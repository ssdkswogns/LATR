import numpy as np
# from mmcv.utils import Config
from mmengine.config import Config, read_base

with read_base():
    from .._base_.base_res101_bs16xep100 import *
    from .._base_.optimizer import *

mod = 'release_iccv/latr_1000_baseline_lite'
mean = [0.485, 0.456, 0.406]
std = [0.229, 0.224, 0.225]

dataset = '1000'
dataset_dir = './data/openlane/images/'
data_dir = './data/openlane/lane3d_1000/'
inference_dataset_dir = './data/TCAR/images/'

batch_size = 1
nworkers = 10
num_category = 21
pos_threshold = 0.3

clip_grad_norm = 20

top_view_region = [[-10, 103], [10, 103], [-10, 3], [10, 3]]
enlarge_length = 20
position_range = [
    top_view_region[0][0] - enlarge_length,
    top_view_region[2][1] - enlarge_length,
    -5,
    top_view_region[1][0] + enlarge_length,
    top_view_region[0][1] + enlarge_length,
    5.]
# anchor_y_steps = np.linspace(3, 103, 20)
anchor_y_steps = [
    3.0, 8.263157894736842, 13.526315789473685, 18.789473684210527,
    24.05263157894737, 29.31578947368421, 34.578947368421055, 39.8421052631579,
    45.10526315789474, 50.36842105263158, 55.63157894736842, 60.89473684210526,
    66.15789473684211, 71.42105263157895, 76.6842105263158, 81.94736842105263,
    87.21052631578948, 92.47368421052632, 97.73684210526316, 103.0
]
num_y_steps = len(anchor_y_steps)

# extra aug
photo_aug = dict(
    brightness_delta=32 // 2,
    contrast_range=(0.5, 1.5),
    saturation_range=(0.5, 1.5),
    hue_delta=9)

_dim_ = 256
num_query = 40
num_pt_per_line = 20
latr_cfg = dict(
    fpn_dim = _dim_,
    num_query = num_query,
    num_group = 1,
    sparse_num_group = 4,
    encoder = dict(
        type='ResNet',
        depth=50,
        num_stages=4,
        out_indices=(1, 2, 3),
        frozen_stages=1,
        norm_cfg=dict(type='BN2d', requires_grad=False),
        norm_eval=True,
        style='caffe',
        dcn=dict(type='DCNv2', deform_groups=1, fallback_on_stride=False),
        stage_with_dcn=(False, False, True, True),
        init_cfg=dict(type='Pretrained', checkpoint='torchvision://resnet50')
    ),
    neck = dict(
        type='FPN',
        in_channels=[512, 1024, 2048],
        out_channels=_dim_,
        start_level=0,
        add_extra_convs='on_output',
        num_outs=4,
        relu_before_extra_convs=True
    ),
    head=dict(
        pt_as_query=True,
        num_pt_per_line=num_pt_per_line,
        xs_loss_weight=2.0,
        zs_loss_weight=10.0,
        vis_loss_weight=1.0,
        cls_loss_weight=10,
        project_loss_weight=1.0,
    ),
    trans_params=dict(init_z=0, bev_h=150, bev_w=70),
)

ms2one=dict(
    type='DilateNaive',
    inc=_dim_, outc=_dim_, num_scales=4,
    dilations=(1, 2, 5, 9))

transformer=dict(
    type='LATRTransformer',
    decoder=dict(
        type='LATRTransformerDecoder',
        embed_dims=_dim_,
        num_layers=2,
        enlarge_length=enlarge_length,
        M_decay_ratio=1,
        num_query=num_query,
        num_anchor_per_query=num_pt_per_line,
        anchor_y_steps=anchor_y_steps,
        transformerlayers=dict(
            type='LATRDecoderLayer',
            attn_cfgs=[
                dict(
                    type='MultiheadAttention',
                    embed_dims=_dim_,
                    num_heads=4,
                    dropout=0.1),
                dict(
                    type='MSDeformableAttention3D',
                    embed_dims=_dim_,
                    num_heads=4,
                    num_levels=1,
                    num_points=8,
                    batch_first=False,
                    num_query=num_query,
                    num_anchor_per_query=num_pt_per_line,
                    anchor_y_steps=anchor_y_steps,
                    dropout=0.1),
                ],
            ffn_cfgs=dict(
                type='FFN',
                embed_dims=_dim_,
                feedforward_channels=_dim_*8,
                num_fcs=2,
                ffn_drop=0.1,
                act_cfg=dict(type='ReLU', inplace=True),
            ),
            feedforward_channels=_dim_ * 8,
            operation_order=('self_attn', 'norm', 'cross_attn', 'norm',
                            'ffn', 'norm')),
))

sparse_ins_decoder=Config(
    dict(
        encoder=dict(
            out_dims=_dim_),
        decoder=dict(
            num_query=latr_cfg['num_query'],
            num_group=latr_cfg['num_group'],
            sparse_num_group=latr_cfg['sparse_num_group'],
            hidden_dim=_dim_,
            kernel_dim=_dim_,
            num_classes=num_category,
            num_convs=4,
            output_iam=True,
            scale_factor=1.,
            ce_weight=2.0,
            mask_weight=5.0,
            dice_weight=2.0,
            objectness_weight=1.0,
        ),
        sparse_decoder_weight=5.0,
))


resize_h = 720
resize_w = 960

nepochs = 24
eval_freq = 8
optimizer_cfg = dict(
    type='AdamW',
    lr=2e-4,
    paramwise_cfg=dict(
        custom_keys={
            'sampling_offsets': dict(lr_mult=0.1),
        }),
    weight_decay=0.01)