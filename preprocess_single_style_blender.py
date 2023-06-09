import os
from argparse import ArgumentParser
import json

from tqdm import tqdm
from PIL import Image
import numpy as np
import torch
from torchvision import transforms
from torchvision.utils import save_image

import utils

def parse_args():
    parser = ArgumentParser()
    parser.add_argument('--out_dir', type=str)
    parser.add_argument('--overwrite', action='store_true')
    parser.add_argument('--blender_dir', type=str)
    parser.add_argument('--style_img', type=str)
    parser.add_argument('--alpha', type=float, default=1)
    parser.add_argument('--bkgd', action='store_true')
    parser.add_argument('--model', type=str)
    parser.add_argument('--device', type=str, default='cpu')
    return parser.parse_args()

def main(args):
    os.makedirs(args.out_dir, exist_ok=args.overwrite)

    # Load style transfer model
    model = torch.load(args.model, map_location=args.device)

    # Transformation
    mean = [0.485, 0.456, 0.406]
    std = [0.229, 0.224, 0.225]
    o_tfm = transforms.Compose([
              transforms.ToTensor(),
              transforms.Normalize(mean=mean, std=std)
            ])
    s_tfm = transforms.Compose([
                transforms.ToTensor(),
                transforms.Resize(800, antialias=False),
                transforms.CenterCrop((800, 800)),
                transforms.Normalize(mean=mean, std=std)
            ])

    # Load style image
    s_img = Image.open(args.style_img).convert('RGB')
    s_img = s_tfm(s_img).unsqueeze(dim=0).to(args.device)
    save_image(
        utils.dataloader.denorm(
            s_img.squeeze().to('cpu'),
        ),
        os.path.join(args.out_dir, 'style.jpg'),
    )
    s_feat = model.enc(s_img)
    s_means, s_stds = model.adain.cal_mean_std(s_feat)
    s_style = torch.concat([s_means.flatten(), s_stds.flatten()])
    np.save(
        os.path.join(args.out_dir, 'style.npy'),
        s_style.cpu().numpy(),
    )

    def style_transfer_dir(sfx):
        os.makedirs(
            os.path.join(args.out_dir, sfx),
            exist_ok=args.overwrite
        )
        with open(
                os.path.join(
                    args.blender_dir,
                    f'transforms_{sfx}.json'
                ),
                'r'
             )  as f:
            train_meta = json.load(f)
        with open(
                os.path.join(
                    args.out_dir,
                    f'transforms_{sfx}.json',
                ),
                'w'
             ) as f:
            f.write(json.dumps(train_meta, indent=2))
        for frame in tqdm(train_meta['frames'], ncols=50):
            o_fname = os.path.join(
                        args.blender_dir,
                        frame['file_path']+'.png'
                      )
            s_fname = os.path.join(
                        args.out_dir,
                        frame['file_path']+'.png'
                      )
            c_img = Image.open(o_fname).convert('RGBA')
            alpha = transforms.functional.to_tensor(
                        c_img
                    )[3]
            c_img = c_img.convert('RGB')
            c_img = o_tfm(c_img).unsqueeze(dim=0).to(args.device)
            t_img = model(c_img, s_img, return_hidden=False, alpha=args.alpha)
            if args.bkgd:
                t_img = utils.dataloader.denorm(
                    t_img.squeeze().to('cpu')
                )
                t_img = torch.concat(
                    [t_img, alpha.unsqueeze(dim=0)], dim=0
                )
            else:
                t_img = utils.dataloader.denorm(
                    t_img.squeeze().to('cpu')
                )
            save_image(t_img, s_fname)
    with torch.no_grad():
        style_transfer_dir('train')
        style_transfer_dir('val')
        style_transfer_dir('test')

if __name__ == '__main__':
    args = parse_args()
    main(args)
