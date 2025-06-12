import torch
import torch.nn as nn
import torch.nn.functional as F
from utils.utils import *
# from mmdet3d.models import build_backbone, build_neck
from mmdet.models import *
from mmdet.registry import MODELS
from .latr_head import LATRHead
from mmengine.config import Config
from .ms2one import build_ms2one
from .utils import deepFeatureExtractor_EfficientNet

# from mmdet.models.builder import BACKBONES


# overall network
class LATR(nn.Module):
    def __init__(self, args):
        super().__init__()
        self.no_cuda = args.no_cuda
        self.batch_size = args.batch_size
        self.num_lane_type = 1  # no centerline
        self.num_y_steps = args.num_y_steps
        self.max_lanes = args.max_lanes
        self.num_category = args.num_category
        _dim_ = args.latr_cfg.fpn_dim
        num_query = args.latr_cfg.num_query
        num_group = args.latr_cfg.num_group
        sparse_num_group = args.latr_cfg.sparse_num_group

        self.encoder = MODELS.build(args.latr_cfg.encoder)
        if getattr(args.latr_cfg, 'neck', None):
            self.neck = MODELS.build(args.latr_cfg.neck)
        else:
            self.neck = None
        self.encoder.init_weights()
        self.ms2one = build_ms2one(args.ms2one)

        # build 2d query-based instance seg
        self.head = LATRHead(
            args=args,
            dim=_dim_,
            num_group=num_group,
            num_convs=4,
            in_channels=_dim_,
            kernel_dim=_dim_,
            position_range=args.position_range,
            top_view_region=args.top_view_region,
            positional_encoding=dict(
                type='SinePositionalEncoding',
                num_feats=_dim_// 2, normalize=True),
            num_query=num_query,
            pred_dim=self.num_y_steps,
            num_classes=args.num_category,
            embed_dims=_dim_,
            transformer=args.transformer,
            sparse_ins_decoder=args.sparse_ins_decoder,
            **args.latr_cfg.get('head', {}),
            trans_params=args.latr_cfg.get('trans_params', {})
        )

    def forward(self, image, _M_inv=None, is_training=True, extra_dict=None):
        # if torch.isnan(image).any() or torch.isinf(image).any():
        #     print("⚠️ Image tensor contains NaN or Inf!")
        #     exit()
        out_featList = self.encoder(image)
        first_neck_out = self.neck(out_featList)
        neck_out = self.ms2one(first_neck_out)

        output = self.head(
            dict(
                x=neck_out,
                lane_idx=extra_dict['seg_idx_label'],
                seg=extra_dict['seg_label'],
                lidar2img=extra_dict['lidar2img'],
                pad_shape=extra_dict['pad_shape'],
                ground_lanes=extra_dict['ground_lanes'] if is_training else None,
                ground_lanes_dense=extra_dict['ground_lanes_dense'] if is_training else None,
                image=image,
            ),
            is_training=is_training,
        )

        # output['out_featList'] = out_featList  # encoder output 전체 리스트
        # output['first_neck_out'] = first_neck_out         # neck 결과
        # output['neck_out'] = neck_out

        # return output

        return {
            "all_cls_scores": output["all_cls_scores"],
            "all_line_preds": output["all_line_preds"]
        }
    
class LATRBackboneOnly(nn.Module):
    def __init__(self, latr_model: LATR):
        super().__init__()
        self.encoder = latr_model.encoder
        self.neck = latr_model.neck
        self.ms2one = latr_model.ms2one

    def forward(self, image):
        out_featList = self.encoder(image)
        first_neck_out = self.neck(out_featList)
        neck_out = self.ms2one(first_neck_out)
        return neck_out