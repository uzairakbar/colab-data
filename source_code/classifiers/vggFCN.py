import os.path as osp

#import fcn
import numpy as np
import torch
import torch.nn as nn

def get_upsampling_weight(in_channels, out_channels, kernel_size):
    """Make a 2D bilinear kernel suitable for upsampling"""
    factor = (kernel_size + 1) // 2
    if kernel_size % 2 == 1:
        center = factor - 1
    else:
        center = factor - 0.5
    og = np.ogrid[:kernel_size, :kernel_size]
    filt = (1 - abs(og[0] - center) / factor) * \
           (1 - abs(og[1] - center) / factor)
    weight = np.zeros((in_channels, out_channels, kernel_size, kernel_size),
                      dtype=np.float64)
    weight[range(in_channels), range(out_channels), :, :] = filt
    return torch.from_numpy(weight).float()


class VGG32s(nn.Module):

    def __init__(self, n_class=23):
        super(VGG32s, self).__init__()
        # conv1
        self.conv1_1 = nn.Conv2d(3, 64, 3, padding=100)
        self.relu1_1 = nn.ReLU(inplace=True)
        self.conv1_2 = nn.Conv2d(64, 64, 3, padding=1)
        self.relu1_2 = nn.ReLU(inplace=True)
        self.pool1 = nn.MaxPool2d(2, stride=2, ceil_mode=True)  # 1/2

        # conv2
        self.conv2_1 = nn.Conv2d(64, 128, 3, padding=1)
        self.relu2_1 = nn.ReLU(inplace=True)
        self.conv2_2 = nn.Conv2d(128, 128, 3, padding=1)
        self.relu2_2 = nn.ReLU(inplace=True)
        self.pool2 = nn.MaxPool2d(2, stride=2, ceil_mode=True)  # 1/4

        # conv3
        self.conv3_1 = nn.Conv2d(128, 256, 3, padding=1)
        self.relu3_1 = nn.ReLU(inplace=True)
        self.conv3_2 = nn.Conv2d(256, 256, 3, padding=1)
        self.relu3_2 = nn.ReLU(inplace=True)
        self.conv3_3 = nn.Conv2d(256, 256, 3, padding=1)
        self.relu3_3 = nn.ReLU(inplace=True)
        self.pool3 = nn.MaxPool2d(2, stride=2, ceil_mode=True)  # 1/8

        # conv4
        self.conv4_1 = nn.Conv2d(256, 512, 3, padding=1)
        self.relu4_1 = nn.ReLU(inplace=True)
        self.conv4_2 = nn.Conv2d(512, 512, 3, padding=1)
        self.relu4_2 = nn.ReLU(inplace=True)
        self.conv4_3 = nn.Conv2d(512, 512, 3, padding=1)
        self.relu4_3 = nn.ReLU(inplace=True)
        self.pool4 = nn.MaxPool2d(2, stride=2, ceil_mode=True)  # 1/16

        # conv5
        self.conv5_1 = nn.Conv2d(512, 512, 3, padding=1)
        self.relu5_1 = nn.ReLU(inplace=True)
        self.conv5_2 = nn.Conv2d(512, 512, 3, padding=1)
        self.relu5_2 = nn.ReLU(inplace=True)
        self.conv5_3 = nn.Conv2d(512, 512, 3, padding=1)
        self.relu5_3 = nn.ReLU(inplace=True)
        self.pool5 = nn.MaxPool2d(2, stride=2, ceil_mode=True)  # 1/32

        # fc6
        self.fc6 = nn.Conv2d(512, 4096, 7)
        self.relu6 = nn.ReLU(inplace=True)
        self.drop6 = nn.Dropout2d(p=0.2)

        # fc7
        self.fc7 = nn.Conv2d(4096, 4096, 1)
        self.relu7 = nn.ReLU(inplace=True)
        self.drop7 = nn.Dropout2d(p=0.2)

        self.score_fr = nn.Conv2d(4096, n_class, 1)
        self.relu_fr = nn.ReLU(inplace=True)
        self.upscore = nn.ConvTranspose2d(n_class, n_class, 64, stride=32)

        self._initialize_weights()

    def _initialize_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                torch.nn.init.xavier_normal_(m.weight, gain=2)
                # torch.nn.init.xavier_normal_(m.bias, gain=2)
            if isinstance(m, nn.ConvTranspose2d):
                assert m.kernel_size[0] == m.kernel_size[1]
                initial_weight = get_upsampling_weight(
                    m.in_channels, m.out_channels, m.kernel_size[0])
                m.weight.data.copy_(initial_weight)
                # torch.nn.init.xavier_normal_(m.bias, gain=2)

    def forward(self, x):
        h = x
        h = self.relu1_1(self.conv1_1(h))
        h = self.relu1_2(self.conv1_2(h))
        h = self.pool1(h)

        h = self.relu2_1(self.conv2_1(h))
        h = self.relu2_2(self.conv2_2(h))
        h = self.pool2(h)

        h = self.relu3_1(self.conv3_1(h))
        h = self.relu3_2(self.conv3_2(h))
        h = self.relu3_3(self.conv3_3(h))
        h = self.pool3(h)

        h = self.relu4_1(self.conv4_1(h))
        h = self.relu4_2(self.conv4_2(h))
        h = self.relu4_3(self.conv4_3(h))
        h = self.pool4(h)

        h = self.relu5_1(self.conv5_1(h))
        h = self.relu5_2(self.conv5_2(h))
        h = self.relu5_3(self.conv5_3(h))
        h = self.pool5(h)

        h = self.relu6(self.fc6(h))
        h = self.drop6(h)

        h = self.relu7(self.fc7(h))
        h = self.drop7(h)

        h = self.relu_fr(self.score_fr(h))

        h = self.upscore(h)
        pad2_out = int((h.size()[2] - x.size()[2])/2)
        pad3_out = int((h.size()[3] - x.size()[3])/2)
        h = h[:, :, pad2_out:pad2_out+x.size()[2], pad3_out:pad3_out+x.size()[3]].contiguous()
        return h

    def copy_params_from_vgg16(self, vgg16):
        features = [
            self.conv1_1, self.relu1_1,
            self.conv1_2, self.relu1_2,
            self.pool1,
            self.conv2_1, self.relu2_1,
            self.conv2_2, self.relu2_2,
            self.pool2,
            self.conv3_1, self.relu3_1,
            self.conv3_2, self.relu3_2,
            self.conv3_3, self.relu3_3,
            self.pool3,
            self.conv4_1, self.relu4_1,
            self.conv4_2, self.relu4_2,
            self.conv4_3, self.relu4_3,
            self.pool4,
            self.conv5_1, self.relu5_1,
            self.conv5_2, self.relu5_2,
            self.conv5_3, self.relu5_3,
            self.pool5,
        ]

        for l1, l2 in zip(vgg16.features, features):
            if isinstance(l1, nn.Conv2d) and isinstance(l2, nn.Conv2d):
                assert l1.weight.size() == l2.weight.size()
                assert l1.bias.size() == l2.bias.size()
                l2.weight.data = l1.weight.data
                l2.bias.data = l1.bias.data

        for i, name in zip([0, 3], ['fc6', 'fc7']):
            l1 = vgg16.classifier[i]
            l2 = getattr(self, name)
            l2.weight.data = l1.weight.data.view(l2.weight.size())
            l2.bias.data = l1.bias.data.view(l2.bias.size())

        return

    def freeze_shallow_layers(self, freeze=True):
        features = [
            self.conv1_1, self.relu1_1,
            self.conv1_2, self.relu1_2,
            self.pool1,
            self.conv2_1, self.relu2_1,
            self.conv2_2, self.relu2_2,
            self.pool2,
            self.conv3_1, self.relu3_1,
            self.conv3_2, self.relu3_2,
            self.conv3_3, self.relu3_3,
            self.pool3,
            self.conv4_1, self.relu4_1,
            self.conv4_2, self.relu4_2,
            self.conv4_3, self.relu4_3,
            self.pool4,
            self.conv5_1, self.relu5_1,
            self.conv5_2, self.relu5_2,
            self.conv5_3, self.relu5_3,
            self.pool5,
        ]

        for l in features:
            if isinstance(l, nn.Conv2d):
                l.weight.requires_grad = not(freeze)
                l.bias.requires_grad = not(freeze)

        l = getattr(self, 'fc6')
        l.weight.requires_grad = not(freeze)
        l.bias.requires_grad = not(freeze)


    def save(self, path):
        """
        Save model with its parameters to the given path. Conventionally the
        path should end with "*.model".
        Inputs:
        - path: path string
        """
        print('Saving model... %s' % path)
        torch.save(self, path)

    @property
    def is_cuda(self):
        """
        Check if model parameters are allocated on the GPU.
        """
        return next(self.parameters()).is_cuda





class VGG8s(VGG32s):

    def __init__(self, n_class=23):
        super(VGG8s, self).__init__()
        # conv1
        self.conv1_1 = nn.Conv2d(3, 64, 3, padding=100)
        self.relu1_1 = nn.ReLU(inplace=True)
        self.conv1_2 = nn.Conv2d(64, 64, 3, padding=1)
        self.relu1_2 = nn.ReLU(inplace=True)
        self.pool1 = nn.MaxPool2d(2, stride=2, ceil_mode=True)  # 1/2

        # conv2
        self.conv2_1 = nn.Conv2d(64, 128, 3, padding=1)
        self.relu2_1 = nn.ReLU(inplace=True)
        self.conv2_2 = nn.Conv2d(128, 128, 3, padding=1)
        self.relu2_2 = nn.ReLU(inplace=True)
        self.pool2 = nn.MaxPool2d(2, stride=2, ceil_mode=True)  # 1/4

        # conv3
        self.conv3_1 = nn.Conv2d(128, 256, 3, padding=1)
        self.relu3_1 = nn.ReLU(inplace=True)
        self.conv3_2 = nn.Conv2d(256, 256, 3, padding=1)
        self.relu3_2 = nn.ReLU(inplace=True)
        self.conv3_3 = nn.Conv2d(256, 256, 3, padding=1)
        self.relu3_3 = nn.ReLU(inplace=True)
        self.pool3 = nn.MaxPool2d(2, stride=2, ceil_mode=True)  # 1/8

        # conv4
        self.conv4_1 = nn.Conv2d(256, 512, 3, padding=1)
        self.relu4_1 = nn.ReLU(inplace=True)
        self.conv4_2 = nn.Conv2d(512, 512, 3, padding=1)
        self.relu4_2 = nn.ReLU(inplace=True)
        self.conv4_3 = nn.Conv2d(512, 512, 3, padding=1)
        self.relu4_3 = nn.ReLU(inplace=True)
        self.pool4 = nn.MaxPool2d(2, stride=2, ceil_mode=True)  # 1/16

        # conv5
        self.conv5_1 = nn.Conv2d(512, 512, 3, padding=1)
        self.relu5_1 = nn.ReLU(inplace=True)
        self.conv5_2 = nn.Conv2d(512, 512, 3, padding=1)
        self.relu5_2 = nn.ReLU(inplace=True)
        self.conv5_3 = nn.Conv2d(512, 512, 3, padding=1)
        self.relu5_3 = nn.ReLU(inplace=True)
        self.pool5 = nn.MaxPool2d(2, stride=2, ceil_mode=True)  # 1/32

        # fc6
        self.fc6 = nn.Conv2d(512, 4096, 7)
        self.relu6 = nn.ReLU(inplace=True)
        self.drop6 = nn.Dropout2d(p=0.2)

        # fc7
        self.fc7 = nn.Conv2d(4096, 4096, 1)
        self.relu7 = nn.ReLU(inplace=True)
        self.drop7 = nn.Dropout2d(p=0.2)


        self.score_fr8 = nn.Conv2d(256, n_class, 1)
        self.score_fr16 = nn.Conv2d(512, n_class, 1)
        self.score_fr32 = nn.Conv2d(4096, n_class, 1)

        self.relu_fr8 = nn.ReLU(inplace=True)
        self.relu_fr16 = nn.ReLU(inplace=True)
        self.relu_fr32 = nn.ReLU(inplace=True)

        self.upscore32 = nn.ConvTranspose2d(
            n_class, n_class, 4, stride=2)
        self.upscore16 = nn.ConvTranspose2d(
            n_class, n_class, 4, stride=2)
        self.upscore8 = nn.ConvTranspose2d(
            n_class, n_class, 16, stride=8)

        self._initialize_weights()

    def forward(self, x):
        h = x
        h = self.relu1_1(self.conv1_1(h))
        h = self.relu1_2(self.conv1_2(h))
        h = self.pool1(h)

        h = self.relu2_1(self.conv2_1(h))
        h = self.relu2_2(self.conv2_2(h))
        h = self.pool2(h)

        h = self.relu3_1(self.conv3_1(h))
        h = self.relu3_2(self.conv3_2(h))
        h = self.relu3_3(self.conv3_3(h))
        h = self.pool3(h)
        h8 = h  # 1/8


        h = self.relu4_1(self.conv4_1(h))
        h = self.relu4_2(self.conv4_2(h))
        h = self.relu4_3(self.conv4_3(h))
        h = self.pool4(h)
        h16 = h  # 1/16


        h = self.relu5_1(self.conv5_1(h))
        h = self.relu5_2(self.conv5_2(h))
        h = self.relu5_3(self.conv5_3(h))
        h = self.pool5(h)

        h = self.relu6(self.fc6(h))
        h = self.drop6(h)

        h = self.relu7(self.fc7(h))
        h = self.drop7(h)
        h32 = h

        h8 = self.relu_fr8(self.score_fr8(h8 * 0.0001))
        h16 = self.relu_fr16(self.score_fr16(h16 * 0.01))
        h32 = self.relu_fr16(self.score_fr32(h32))

        h = h32
        h = self.upscore32(h)

        pad2_16 = int((h16.size()[2] - h.size()[2])/2)
        pad3_16 = int((h16.size()[3] - h.size()[3])/2)
        h16 = h16[:, :, pad2_16:pad2_16+h.size()[2], pad3_16:pad3_16+h.size()[3]]
        h = h + h16
        h = self.upscore16(h)

        pad2_8 = int((h8.size()[2] - h.size()[2])/2)
        pad3_8 = int((h8.size()[3] - h.size()[3])/2)
        h8 = h8[:, :, pad2_8:pad2_8+h.size()[2], pad3_8:pad3_8+h.size()[3]]
        h = h + h8
        h = self.upscore8(h)

        pad2_out = int((h.size()[2] - x.size()[2])/2)
        pad3_out = int((h.size()[3] - x.size()[3])/2)
        h = h[:, :, pad2_out:pad2_out+x.size()[2], pad3_out:pad3_out+x.size()[3]].contiguous()
        return h

from torchvision import models

class VGG32sPrune(VGG32s):
    def __init__(self, n_class = 24):
        super(VGG32sPrune, self).__init__()
        # model = models.vgg16(pretrained=False)
        # self.features = model.features

        self.features = nn.Sequential(self.conv1_1, self.relu1_1,
                                      self.conv1_2, self.relu1_2,
                                      self.pool1,
                                      self.conv2_1, self.relu2_1,
                                      self.conv2_2, self.relu2_2,
                                      self.pool2,
                                      self.conv3_1, self.relu3_1,
                                      self.conv3_2, self.relu3_2,
                                      self.conv3_3, self.relu3_3,
                                      self.pool3,
                                      self.conv4_1, self.relu4_1,
                                      self.conv4_2, self.relu4_2,
                                      self.conv4_3, self.relu4_3,
                                      self.pool4,
                                      self.conv5_1, self.relu5_1,
                                      self.conv5_2, self.relu5_2,
                                      self.conv5_3, self.relu5_3,
                                      self.pool5)

        for param in self.features.parameters():
        	param.requires_grad = False

        self.segmenter = nn.Sequential(nn.Dropout2d(p=0.15),
                                       nn.Conv2d(512, 4096, 7),
                                       nn.ReLU(inplace=True),
                                       nn.Dropout2d(p=0.15),
                                       nn.Conv2d(4096, 4096, 1),
                                       nn.ReLU(inplace=True),
                                       nn.Dropout2d(p=0.15),
                                       nn.Conv2d(4096, n_class, 1),
                                       nn.ReLU(inplace=True),
                                       nn.ConvTranspose2d(n_class, n_class, 64, stride=32))

        self._initialize_weights()
        self.copy_params_from_vgg16()

    def copy_params_from_vgg16(self, vgg16=None):
        if vgg16 is None:
            vgg16 = models.vgg16(pretrained=True)
        
        for l1, l2 in zip(vgg16.features, self.features):
            if isinstance(l1, nn.Conv2d) and isinstance(l2, nn.Conv2d):
                assert l1.weight.size() == l2.weight.size()
                assert l1.bias.size() == l2.bias.size()
                l2.weight.data = l1.weight.data
                l2.bias.data = l1.bias.data

        for i, j in zip([0, 3], [1, 4]):
            l1 = vgg16.classifier[i]
            l2 = self.segmenter[j]
            l2.weight.data = l1.weight.data.view(l2.weight.size())
            l2.bias.data = l1.bias.data.view(l2.bias.size())

        return

    def forward(self, x):
        h = self.features(x)
        h = self.segmenter(h)

        pad2_out = int((h.size()[2] - x.size()[2])/2)
        pad3_out = int((h.size()[3] - x.size()[3])/2)
        h = h[:, :, pad2_out:pad2_out+x.size()[2], pad3_out:pad3_out+x.size()[3]].contiguous()
        return h
