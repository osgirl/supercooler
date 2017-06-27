import os
import sys
import copy
import itertools

import numpy as np
import cv2

CAMERA_IDS = [ 0, 1, 2, 3, 7, 6, 5, 4, 8, 9, 10, 11 ]
'''FS_READ = cv2.FileStorage('transform_data.xml', 0) '''

'''def drawResultPoints(img, pts):
    out = copy.copy(img)
    for bottle in pts:
        (x,y) = pts[bottle]
        radius = 8
        thickness = 3
        color = (255,0,0) #blue
        cv2.circle(out, (int(x),int(y)), radius, color, thickness)
    return out

def drawMatches(img1, src_pts, img2, dst_pts):
    img1 = cv2.cvtColor(img1,cv2.COLOR_BGR2GRAY)
    img2 = cv2.cvtColor(img2,cv2.COLOR_BGR2GRAY)

    rows1 = img1.shape[0]
    cols1 = img1.shape[1]
    rows2 = img2.shape[0]
    cols2 = img2.shape[1]

    out = np.zeros((max([rows1,rows2]),cols1+cols2,3), dtype='uint8')

    out[:rows1,:cols1] = np.dstack([img1, img1, img1])
    out[:rows2,cols1:] = np.dstack([img2, img2, img2])

    for (x1,y1), (x2,y2) in zip(src_pts, dst_pts):
        radius = 8
        thickness = 3
        color = (255,0,0) #blue
        cv2.circle(out, (int(x1),int(y1)), radius, color, thickness)
        cv2.circle(out, (int(x2)+cols1,int(y2)), radius, color, thickness)
        cv2.line(out, (int(x1),int(y1)), (int(x2)+cols1,int(y2)), color, thickness)

    return out'''

def get_shelf_coords(local_coords):

    FS_READ = cv2.FileStorage('transform_data.xml', 0) 

    #if len(sys.argv) < 2: print 'usage: %s dir' % (sys.argv[0]); sys.exit()
    #else: in_dir = sys.argv[1]

    '''in_dir = 'Bn_bottles_numbered'

    image_points = []
    imageList    = []

    # read images
    for cam_id in CAMERA_IDS:
        img = cv2.imread(os.path.join(in_dir, 'B%d_1.png' % (cam_id)))
        imageList.append(img)

    resultImage = imageList[0]'''

    resultPoints = local_coords[CAMERA_IDS[0]]

    for index2 in range(1,12):

        '''image1 = copy.copy(imageList[index2 - 1])
        image2 = copy.copy(imageList[index2])'''

        cam_id2 = CAMERA_IDS[index2  ]

        '''xMin = int(FS_READ.getNode('xMin_%d' % (index2)).real())
        xMax = int(FS_READ.getNode('xMax_%d' % (index2)).real())
        yMin = int(FS_READ.getNode('yMin_%d' % (index2)).real())
        yMax = int(FS_READ.getNode('yMax_%d' % (index2)).real())'''
        
        translation = FS_READ.getNode('translation_%d' % (index2)).mat()
        H = A = None

        try:    A = FS_READ.getNode('A_%d' % (index2)).mat()
        except: 
            try: 
                H = FS_READ.getNode('H_%d' % (index2)).mat()
                print 'no rigid transform available; loading homography'
            except: print 'no data available for camera %d' % (index2)
       
        '''warpedResImg = cv2.warpPerspective(resultImage, translation, (xMax-xMin, yMax-yMin))'''

        for bottle in resultPoints:
            resultPoints[bottle] = cv2.perspectiveTransform(np.array([[resultPoints[bottle]]]), translation)[0][0]

        if A is None:
            fullTransformation = np.dot(translation,H) #again, images must be translated to be 100% visible in new canvas
            '''warpedImage2 = cv2.warpPerspective(image2, fullTransformation, (xMax-xMin, yMax-yMin))'''

            for bottle in local_coords[cam_id2]:
                local_coords[cam_id2][bottle] = cv2.perspectiveTransform(
                    np.array([[local_coords[cam_id2][bottle]]]), fullTransformation)[0][0]
        else:
            '''warpedImageTemp = cv2.warpPerspective(image2, translation, (xMax-xMin, yMax-yMin))
            warpedImage2 = cv2.warpAffine(warpedImageTemp, A, (xMax-xMin, yMax-yMin))'''

            for bottle in local_coords[cam_id2]:
                tmp = cv2.perspectiveTransform(np.array([[local_coords[cam_id2][bottle]]]), translation)[0][0]
                local_coords[cam_id2][bottle] = cv2.transform(
                    np.array([[tmp]]), A)[0][0]
            
        '''imageList[index2] = copy.copy(warpedImage2) #crucial: update old images for future feature extractions

        resGray = cv2.cvtColor(resultImage,cv2.COLOR_BGR2GRAY)
        warpedResGray = cv2.warpPerspective(resGray, translation, (xMax-xMin, yMax-yMin))

        ret, mask1 = cv2.threshold(warpedResGray,1,255,cv2.THRESH_BINARY_INV)
        mask3 = np.float32(mask1)/255

        #apply mask
        warpedImage2[:,:,0] = warpedImage2[:,:,0]*mask3
        warpedImage2[:,:,1] = warpedImage2[:,:,1]*mask3
        warpedImage2[:,:,2] = warpedImage2[:,:,2]*mask3

        result = warpedResImg + warpedImage2'''

        for bottle in local_coords[cam_id2]:
            resultPoints[bottle] = local_coords[cam_id2][bottle]
        
        #cv2.imshow('sedf', result)
        #cv2.waitKey()
        
        '''resultImage = result
        cv2.imwrite("results/intermediateResult"+str(index2)+".png",result)'''

    '''cv2.imwrite("results/finalResult.png", result)
    cv2.imshow('sdf', drawResultPoints(result, resultPoints))
    cv2.waitKey()'''
    FS_READ.release()
    return resultPoints

'''local_coords = [
    {},{},{},
    {0: [636.75227040262848, 292.33823574993005]},
    {}, {}, {}, {}, {}, {}, {}, {}
]

print get_shelf_coords(local_coords)
FS_READ.release()'''
