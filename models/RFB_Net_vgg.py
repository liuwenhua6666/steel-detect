import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.autograd import Variable
from layers import *
import torchvision.transforms as transforms
import torchvision.models as models
import torch.backends.cudnn as cudnn
import os
from models.module import Backbone



class RFBNet(nn.Module):

    def __init__(self, phase, size, head, num_classes):
        super(RFBNet, self).__init__()
        self.phase = phase
        self.num_classes = num_classes
        self.size = size

        self.base = Backbone()

        self.loc = nn.ModuleList(head[0])
        self.conf = nn.ModuleList(head[1])
        if self.phase == 'test':
            self.softmax = nn.Softmax(dim=-1)

    def forward(self, x):
        sources = list()
        loc = list()
        conf = list()

        f1, f2, f3 = self.base(x)

        sources = [f1, f2, f3]

        # apply multibox head to source layers
        for (x, l, c) in zip(sources, self.loc, self.conf):
            loc.append(l(x).permute(0, 2, 3, 1).contiguous())
            conf.append(c(x).permute(0, 2, 3, 1).contiguous())

        loc = torch.cat([o.view(o.size(0), -1) for o in loc], 1)
        conf = torch.cat([o.view(o.size(0), -1) for o in conf], 1)

        if self.phase == "test":
            output = (
                loc.view(loc.size(0), -1, 4),                   # loc preds
                self.softmax(conf.view(-1, self.num_classes)),  # conf preds
            )
        else:
            output = (
                loc.view(loc.size(0), -1, 4),
                conf.view(conf.size(0), -1, self.num_classes),
            )
        return output

    def load_weights(self, base_file):
        other, ext = os.path.splitext(base_file)
        if ext == '.pkl' or '.pth':
            print('Loading weights into state dict...')
            self.load_state_dict(torch.load(base_file))
            print('Finished!')
        else:
            print('Sorry only .pth and .pkl files supported.')

def multibox(num_classes=2):
    # 需要注意，这里要跟 prior_box.py 对应上
    # number of boxes per feature map location，就是各个feature map上预定义的anchor数，可结合prior_box.py；理解
    anchor_num = [1, 1, 1] # number of boxes per feature map location
    loc_layers = []
    conf_layers = []

    ############################ 第1个检测层 ############################
    loc_layers  += [nn.Conv2d(128, anchor_num[0] * 4, kernel_size=3, padding=1)]
    conf_layers += [nn.Conv2d(128, anchor_num[0] * num_classes, kernel_size=3, padding=1)]
    ############################ 第2个检测层 ############################
    loc_layers  += [nn.Conv2d(128, anchor_num[1] * 4, kernel_size=3, padding=1)]
    conf_layers += [nn.Conv2d(128, anchor_num[1] * num_classes, kernel_size=3, padding=1)]
    ############################ 第3个检测层 ############################
    loc_layers  += [nn.Conv2d(128, anchor_num[2] * 4, kernel_size=3, padding=1)]
    conf_layers += [nn.Conv2d(128, anchor_num[2] * num_classes, kernel_size=3, padding=1)]

    return (loc_layers, conf_layers)


def build_net(phase, size=300, num_classes=2):
    if phase != "test" and phase != "train":
        print("Error: Phase not recognized")
        return

    return RFBNet(phase, size, multibox(num_classes), num_classes)

if __name__ == '__main__':
    # 0.966 MB
    x = torch.randn(2, 3, 300, 300)
    net = build_net('test')
    net.eval()
    from thop import profile

    input = torch.randn(1, 3, 300, 300)
    flops, params = profile(net, inputs=(input,))
    from thop import clever_format
    flops, params = clever_format([flops, params], "%.3f")
    print(flops)
    print(params)

    from utils.timer import Timer
    _t = {'im_detect': Timer()}
    for i in range(300):
        _t['im_detect'].tic()
        net.forward(x)
        detect_time = _t['im_detect'].toc()
        print(detect_time)