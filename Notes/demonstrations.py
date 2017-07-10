import cvFunctions as cvf

def real_world_locator_demo():
    print "Initialize Locators for cameras 0, 1 and 4 on shelf D"
    locator0 = cvf.Real_World_Locator("D", 0)
    locator1 = cvf.Real_World_Locator("D", 1)
    locator4 = cvf.Real_World_Locator("D", 4)


    print "At height 12.5, these locations are the square containing number 14 (check Shelf D heights/{height}/undistorted{x}.png)"
    print "camera 0 locates at:", locator0.get_real_world_location(340, 175, 12.5)
    print "camera 1 locates at:", locator1.get_real_world_location(220, 170, 12.5)
    print "camera 4 locates at:", locator4.get_real_world_location(335, 290, 12.5)


    print "At height 24.5, these locations are the square containing number 46 (check Shelf D heights/{height}/undistorted{x}.png)"
    print "camera 0 locates at:", locator0.get_real_world_location(310, 630, 24.5)
    print "camera 1 locates at:", locator1.get_real_world_location(20, 610, 24.5)
    print "camera 4 locates at:", locator4.get_real_world_location(308, 480, 24.5)


def detect_things_demo():
    print "Showing detection for all images in Shelf_C"
    for i in map( lambda x: str(x), range(12) ):
        image_path = "Shelf C/2017-07-02-00-07-41_C_" + i + "_0_raw.png"
        distortion_path = "Shelf D/Distortion Map/Distortion_" + i + ".png"
        image = cvf.read_image(image_path)
        distortion_map = cvf.read_image(distortion_path)
        image = cvf.mapped_lens_correction(image, distortion_map)

        (circles, visualisation) = cvf.bottle_and_can_detection(image)
        cvf.show_image( visualisation, "vis" )



real_world_locator_demo()
detect_things_demo()