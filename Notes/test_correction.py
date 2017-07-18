import argparse
import glob
import os
import re
import cvFunctions as cvf
import matplotlib.pyplot as plt

parser = argparse.ArgumentParser()

parser.add_argument('-i', required=True, dest='in_dir')
parser.add_argument('-s', required=True, dest='shelf')

args = parser.parse_args()
files = glob.glob(os.path.join(args.in_dir, '*' + args.shelf + '*.png'))

for image_path in files:
    filename = os.path.basename(image_path)
    temp = filename[filename.index(args.shelf)+2:]

    camera = re.search('\d+\D', temp).group()[:-1]
    distortion_path = '/home/sam/Freelance/SuperCooler/supercooler/Notes/distortion_new/' + args.shelf + '_20.5_' + camera + '.png'

    print image_path
    print distortion_path + '\n'

    image          = cvf.read_image(image_path)
    distortion_map = cvf.read_image(distortion_path)

    corrected = cvf.mapped_lens_correction(image, distortion_map)

    cvf.show_image(image, 'original')
    plt.imshow(corrected[...,::-1]), plt.show()
