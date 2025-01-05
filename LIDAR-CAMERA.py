import os
from glob import glob
import cv2
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from kitti_utils import *
from ultralytics import YOLO
import torch
import pymap3d as pm
DATA_PATH = r'/Users/badrdiscipline/Downloads/voiceAssistant/2011_10_03-2/2011_10_03_drive_0047_sync'
# get RGB camera data
left_image_paths = sorted(glob(os.path.join(DATA_PATH, 'image_02/data/*.png')))
right_image_paths = sorted(glob(os.path.join(DATA_PATH, 'image_03/data/*.png')))

# get LiDAR data
bin_paths = sorted(glob(os.path.join(DATA_PATH, 'velodyne_points/data/*.bin')))

# get GPS/IMU data
oxts_paths = sorted(glob(os.path.join(DATA_PATH, r'oxts/data**/*.txt')))
with open('/Users/badrdiscipline/Downloads/voiceAssistant/2011_10_03/calib_cam_to_cam.txt','r') as f:
    calib = f.readlines()

# get projection matrices (rectified left camera --> left camera (u,v,z))
P_rect2_cam2 = np.array([float(x) for x in calib[25].strip().split(' ')[1:]]).reshape((3,4))


# get rectified rotation matrices (left camera --> rectified left camera)
R_ref0_rect2 = np.array([float(x) for x in calib[24].strip().split(' ')[1:]]).reshape((3, 3,))

# add (0,0,0) translation and convert to homogeneous coordinates
R_ref0_rect2 = np.insert(R_ref0_rect2, 3, values=[0,0,0], axis=0)
R_ref0_rect2 = np.insert(R_ref0_rect2, 3, values=[0,0,0,1], axis=1)


# get rigid transformation from Camera 0 (ref) to Camera 2
R_2 = np.array([float(x) for x in calib[21].strip().split(' ')[1:]]).reshape((3,3))
t_2 = np.array([float(x) for x in calib[22].strip().split(' ')[1:]]).reshape((3,1))

# get cam0 to cam2 rigid body transformation in homogeneous coordinates
T_ref0_ref2 = np.insert(np.hstack((R_2, t_2)), 3, values=[0,0,0,1], axis=0)
T_velo_ref0 = get_rigid_transformation(r'/Users/badrdiscipline/Downloads/voiceAssistant/2011_10_03/calib_velo_to_cam.txt')
T_imu_velo = get_rigid_transformation(r'/Users/badrdiscipline/Downloads/voiceAssistant/2011_10_03/calib_imu_to_velo.txt')
# transform from velo (LiDAR) to left color camera (shape 3x4)
T_velo_cam2 = P_rect2_cam2 @ R_ref0_rect2 @ T_ref0_ref2 @ T_velo_ref0

# homogeneous transform from left color camera to velo (LiDAR) (shape: 4x4)
T_cam2_velo = np.linalg.inv(np.insert(T_velo_cam2, 3, values=[0,0,0,1], axis=0))
# transform from IMU to left color camera (shape 3x4)
T_imu_cam2 = T_velo_cam2 @ T_imu_velo

# homogeneous transform from left color camera to IMU (shape: 4x4)
T_cam2_imu = np.linalg.inv(np.insert(T_imu_cam2, 3, values=[0,0,0,1], axis=0))
model = YOLO("yolov10s.pt")

# set confidence and IOU thresholds
model.conf = 0.25  # confidence threshold (0-1), default: 0.25
model.iou = 0.25  # NMS IoU threshold (0-1), default: 0.45
def get_uvz_centers(image, velo_uvz, bboxes, draw=True):
    ''' Obtains detected object centers projected to uvz camera coordinates.
        Starts by associating LiDAR uvz coordinates to detected object centers,
        once a match is found, the coordinates are transformed to the uvz
        camera reference and added to the bboxes array.

        NOTE: The image is modified in place so there is no need to return it.

        Inputs:
          image - input image for detection
          velo_uvz - LiDAR coordinates projected to camera reference
          bboxes - xyxy bounding boxes from detections
          draw - (_Bool) draw measured depths on image
        Outputs:
          bboxes_out - modified array containing the object centers projected
                       to uvz image coordinates
        '''


    # Ensure bboxes is a 2D array with shape (num_boxes, 4)
    if bboxes.ndim == 1:
        bboxes = bboxes.reshape(1, -1)  # reshape to 2D if it's 1D

    # unpack LiDAR camera coordinates
    u, v, z = velo_uvz
    depth=[]

    # Initialize output array to hold bounding boxes and uvz
    bboxes_out = np.zeros((bboxes.shape[0], bboxes.shape[1] + 3))  # Add 3 columns for uvz
    bboxes_out[:, :bboxes.shape[1]] = bboxes  # Copy original bounding box data

    # Iterate through all detected bounding boxes
    for i, bbox in enumerate(bboxes):
        # Convert numpy array to PyTorch tensor before using torch.round()
        pt1 = torch.round(torch.tensor(bbox[0:2])).to(torch.int).numpy()  # top-left corner
        pt2 = torch.round(torch.tensor(bbox[2:4])).to(torch.int).numpy()  # bottom-right corner

        # Get center location of the object on the image
        obj_x_center = (pt1[1] + pt2[1]) / 2
        obj_y_center = (pt1[0] + pt2[0]) / 2

        # Now get the closest LiDAR points to the center
        center_delta = np.abs(np.array((v, u)) - np.array([[obj_x_center, obj_y_center]]).T)

        # Choose coordinate pair with the smallest L2 norm (closest LiDAR point)
        min_loc = np.argmin(np.linalg.norm(center_delta, axis=0))


        # Get LiDAR location in image/camera space
        velo_depth = z[min_loc]
        depth.append(velo_depth)  # LiDAR depth in camera space
        uvz_location = np.array([u[min_loc], v[min_loc], velo_depth])

        # Add velo projections (u, v, z) to bboxes_out
        bboxes_out[i, -3:] = uvz_location

        # Draw depth on image at center of each bounding box (optional)
        if draw:
            object_center = (np.round(obj_y_center).astype(int), np.round(obj_x_center).astype(int))
            cv2.putText(image,
                        '{0:.2f} m'.format(velo_depth),
                        object_center,  # Position on image
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.5,  # Font scale
                        (255, 0, 0), 2, cv2.LINE_AA)  # Blue text

    return bboxes_out,depth
def get_detection_coordinates(image, bin_path, draw_boxes=True, draw_depth=True):
    '''Obtains detections for the input image, along with the coordinates of
       the detected object centers. The coordinates obtained are:
       - Camera with depth --> uvz
       - LiDAR/velo --> xyz
       - GPS/IMU --> xyz

    Inputs:
        image - RGB image to run detection on
        bin_path - Path to LiDAR bin file

    Outputs:
        bboxes - Array of detected bounding boxes, confidences, classes
        velo_uvz - LiDAR points projected to camera uvz coordinate frame
        coordinates - Array of all object center coordinates in the frames
                      listed above
    '''
    ## 1. Compute detections in the left image using YOLOv10 model
    results = model(image)
    boxes_xyxy = results[0].boxes.xyxy.cpu().numpy()   # Convert to NumPy array

    detected_image = results[0].plot()  # Use show() to visualize the results (This is for inline display, not return)

    # Get LiDAR points and transform them to image/camera space (uvz coordinates)
    velo_uvz = project_velobin2uvz(bin_path, T_velo_cam2, image, remove_plane=True)

    # Map bounding boxes to LiDAR UVZ coordinates for object centers
    bboxes,depth = get_uvz_centers(image, velo_uvz, boxes_xyxy, draw=draw_depth)

    return bboxes, velo_uvz, detected_image,depth


def imu2geodetic(x, y, z, lat0, lon0, alt0, heading0):
    ''' Converts cartesian IMU coordinates to Geodetic based on current
        location. This function works with x,y,z as vectors and lat0, lon0,
        alt0 as scalars.

        - Correct orientation is provided by the heading
        - The Elevation must be corrected for pymap3d (i.e. 180 is 0 elevation)
        Inputs:
            x - IMU x-coodinate (either scaler of (Nx1) array)
            y - IMU y-coodinate (either scaler of (Nx1) array)
            z - IMU z-coodinate (either scaler of (Nx1) array)
            lat0 - initial Latitude in degrees
            lon0 - initial Longitude in degrees
            alt0 - initial Ellipsoidal Altitude in meters
            heading0 - initial heading in radians (0 - East, positive CCW)
        Outputs:
            lla - (Nx3) numpy array of
        '''
    # convert to RAE
    rng = np.sqrt(x**2 + y**2 + z**2)
    az = np.degrees(np.arctan2(y, x)) + np.degrees(heading0)
    el = np.degrees(np.arctan2(np.sqrt(x**2 + y**2), z)) + 90

    # convert to geodetic
    lla = pm.aer2geodetic(az, el, rng, lat0, lon0, alt0)

    # convert to numpy array
    lla = np.vstack((lla[0], lla[1], lla[2])).T

    return lla
canvas_height = 752
canvas_width = 500

# get consistent center for ego vehicle
ego_center = (250, int(canvas_height*0.95))

# get rectangle coordiantes for ego vehicle
ego_x1 = ego_center[0] - 5
ego_y1 = ego_center[1] - 10
ego_x2 = ego_center[0] + 5
ego_y2 = ego_center[1] + 10

def draw_scenario(canvas, imu_xyz, sf=12):
    # draw ego vehicle
    cv2.rectangle(canvas, (ego_x1, ego_y1), (ego_x2, ego_y2), (0, 255, 0), -1);

    # draw detected objects
    for val in imu_xyz:
        obj_center = (ego_center[0] - sf*int(np.round(val[1])),
                      ego_center[1] - sf*int(np.round(val[0])))
        # cv2.circle(canvas, obj_center, 5, (255, 0, 0), -1);

        # get object rectangle coordinates
        obj_x1 = obj_center[0] - 5
        obj_y1 = obj_center[1] - 10
        obj_x2 = obj_center[0] + 5
        obj_y2 = obj_center[1] + 10

        cv2.rectangle(canvas, (obj_x1, obj_y1), (obj_x2, obj_y2), (255, 0, 0), -1);


    return canvas

get_total_seconds = lambda hms: hms[0]*60*60 + hms[1]*60 + hms[2]


def timestamps2seconds(timestamp_path):
    ''' Reads in timestamp path and returns total seconds (does not account for day rollover). '''
    # Read the CSV file, assuming the timestamps are in the first column
    timestamps = pd.read_csv(timestamp_path, header=None)

    # Extract the time part (HH:MM:SS) from the timestamps
    time_strs = timestamps[0].apply(lambda x: x.split(' ')[1])

    # Split the time into hours, minutes, and seconds
    hours = time_strs.apply(lambda x: x.split(':')[0]).astype(np.float64)
    minutes = time_strs.apply(lambda x: x.split(':')[1]).astype(np.float64)
    seconds = time_strs.apply(lambda x: x.split(':')[2]).astype(np.float64)

    # Stack the hours, minutes, and seconds into an array
    hms_vals = np.vstack((hours, minutes, seconds)).T

    # Convert the time to total seconds
    total_seconds = np.array(list(map(get_total_seconds, hms_vals)))

    return total_seconds
cam2_total_seconds = timestamps2seconds(os.path.join(DATA_PATH, r'image_02/timestamps.txt'))
cam2_fps = 1/np.median(np.diff(cam2_total_seconds))
result_video = []
depth=[]

for index in range(20):
    left_image = cv2.cvtColor(cv2.imread(left_image_paths[index]), cv2.COLOR_BGR2RGB)
    bin_path = bin_paths[index]
    oxts_frame = get_oxts(oxts_paths[index])
    bboxes, velo_uvz,detected_image,depth = get_detection_coordinates(left_image, bin_path)

    # get transformed coordinates
    uvz = bboxes[:, -3:]

    # velo_xyz = transform_uvz(uvz, T_cam2_velo) # we can also get LiDAR coordiantes
    imu_xyz = transform_uvz(uvz, T_cam2_imu) # Replace with your target video path


    # draw velo on blank image
    velo_image = draw_velo_on_image(velo_uvz, np.zeros_like(left_image))
    bboxes, velo_uvz,detected_image,depth = get_detection_coordinates(left_image, bin_path)

    # stack frames
    stacked = np.vstack((detected_image, velo_image))

    # draw top down scenario on canvas
    canvas = np.zeros((canvas_height, canvas_width, 3), dtype=np.uint8)
    draw_scenario(canvas, imu_xyz, sf=12)

    # place everything in a single frame
    frame = np.hstack((stacked,
                       255*np.ones((canvas_height, 1, 3), dtype=np.uint8),
                       canvas))

    # add to result video
    result_video.append(frame)

# get width and height for video frames
h, w, _ = frame.shape
out = cv2.VideoWriter('static/videos/lidar_frame_stack.mp4',
                      cv2.VideoWriter_fourcc(*'mp4v'),
                      cam2_fps,
                      (w, h))

for i in range(len(result_video)):
    out.write(cv2.cvtColor(result_video[i], cv2.COLOR_BGR2RGB))
out.release()
plt.imshow(frame)

