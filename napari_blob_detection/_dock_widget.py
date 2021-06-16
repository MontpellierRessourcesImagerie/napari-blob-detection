"""
This module is an example of a barebones QWidget plugin for napari

It implements the ``napari_experimental_provide_dock_widget`` hook specification.
see: https://napari.org/docs/dev/plugins/hook_specifications.html

Replace code below according to your needs.
"""
import numpy as np
import pandas as pd


from napari_plugin_engine import napari_hook_implementation
from skimage.feature import blob_dog, blob_log, blob_doh
from napari.types import LayerDataTuple, ImageData
from napari.layers import Image, Points
from magicgui import magic_factory
from skimage.draw import disk
from napari import Viewer
from pathlib import Path
from enum import Enum
from math import sqrt



def init(widget):
    
    # this option should only be visible for blob_dog
    widget.sigma_ratio.visible = False
    
    # update available options for each detector
    @widget.detector.changed.connect
    def update_options(event):
        
        if widget.detector.value.value == "blob_log":
            widget.num_sigma.visible = True
            widget.log_scale.visible = True
            widget.sigma_ratio.visible = False
            
        elif widget.detector.value.value == "blob_dog":
            widget.num_sigma.visible = False
            widget.log_scale.visible = False
            widget.sigma_ratio.visible = True
        
            
        elif widget.detector.value.value == "blob_doh":
            widget.num_sigma.visible = True
            widget.log_scale.visible = True
            widget.sigma_ratio.visible = False
            widget.exclude_border.visible = False
            


class Detector(Enum):
    """A set of valid arithmetic operations for image_arithmetic.

    To create nice dropdown menus with magicgui, it's best
    (but not required) to use Enums.  Here we make an Enum
    class for all of the image math operations we want to
    allow.
    """
    # dropdown options for detectors
    LoG = "blob_log"
    DoG = "blob_dog"
    DoH = "blob_doh"

@magic_factory(layer={'tooltip': '2D or 3D ndarray. Input grayscale image, blobs are assumed to be light on dark background (white on black).'},
               detector={'tooltip': 'Detection algorithm to use. LoG = Laplacian of Gaussian, DoG = Difference of Gaussian, DoH = Determinant of Hessian'},
               min_sigma={'tooltip': 'scalar or sequence of scalars, optional. σ \u2248 diameter/(2*√2). The minimum standard deviation for Gaussian kernel. Keep this low to detect smaller blobs. The standard deviations of the Gaussian filter are given for each axis as a sequence, or as a single number, in which case it is equal for all axes.'},
               max_sigma={'tooltip': 'scalar or sequence of scalars, optional. The maximum standard deviation for Gaussian kernel. Keep this high to detect larger blobs. The standard deviations of the Gaussian filter are given for each axis as a sequence, or as a single number, in which case it is equal for all axes.'},
               num_sigma={'tooltip': 'int, optional.The number of intermediate values of standard deviations to consider between min_sigma and max_sigma.'},
               overlap={'tooltip': 'float, optional. A value between 0 and 1. If the area of two blobs overlaps by a fraction greater than threshold, the smaller blob is eliminated.'},
               log_scale={'tooltip': 'bool, optional. If set intermediate values of standard deviations are interpolated using a logarithmic scale to the base 10. If not, linear interpolation is used.'},
               exclude_border={'tooltip': 'tuple of ints, int, or False, optional. If tuple of ints, the length of the tuple must match the input array’s dimensionality. Each element of the tuple will exclude peaks from within exclude_border-pixels of the border of the image along that dimension. If nonzero int, exclude_border excludes peaks from within exclude_border-pixels of the border of the image. If zero or False, peaks are identified regardless of their distance from the border.'},
               call_button="Detect blobs",
               marker={"choices": ['disc', 'ring', 'diamond'], 
                       'tooltip': 'marker to represent the detected blobs'},
               threshold={"step": 10e-15,
                          "tooltip": 'float, optional. The absolute lower bound for scale space maxima. Local maxima smaller than thresh are ignored. Reduce this to detect blobs with less intensities.'},
               widget_init=init)
               
def blob_detection(
    layer: Image,
    viewer: Viewer,
    detector: Detector,
    min_sigma=1.00,
    max_sigma=50.00,
    sigma_ratio=1.6,
    num_sigma=10,
    threshold=0.200000,
    overlap=0.50,
    log_scale=False,
    exclude_border=False,
    marker='disc') -> LayerDataTuple:
    """Detect blobs in image, returny points layer with spots"""
    
    if detector.value == "blob_log":
        result = blob_log(layer.data,
                          min_sigma=min_sigma,
                          max_sigma=max_sigma,
                          num_sigma=num_sigma,
                          threshold=threshold,
                          overlap=overlap,
                          log_scale=log_scale,
                          exclude_border=exclude_border)
    
    elif detector.value == "blob_dog":
        result =  blob_dog(layer.data, min_sigma=min_sigma,
                           max_sigma=max_sigma,
                           sigma_ratio=sigma_ratio,
                           threshold=threshold,
                           overlap=overlap,
                           exclude_border=exclude_border)
    
    elif detector.value == "blob_doh":
        result =  blob_doh(layer.data, min_sigma=min_sigma,
                           max_sigma=max_sigma,
                           num_sigma=num_sigma,
                           threshold=threshold,
                           overlap=overlap,
                           log_scale=log_scale)
        
    # turn results into pd DataFrame
    
    # add empty z-dimension if not present
    
    if result.shape[1] == 3:
        result = np.pad(result, [(0, 0), (1, 0)])
    
    result = pd.DataFrame(result, columns=['z_coordinates',
                                           'y_coordinates',
                                           'x_coordinates',
                                           'size'])
        
    # get radius
    result.iloc[:, -1] = result.iloc[:, -1] * sqrt(2)

    # get spot size
    size = result.iloc[:, -1]*2
    
    output = result.iloc[:, 0:-1].astype(int)
    
    # create filter widget and dock to viewer
    filter_instance = filter_widget()
    viewer.window.add_dock_widget(filter_instance, name="Filter widget") 

    return (output, {'size': size, 'symbol': marker,
                      'name':detector.value, 'opacity': 0.5}, 'points')


def filter_init(widget):
    
    widget.call_button.visible = False
    
    @widget.initialize_filter.changed.connect
    def measure(event):
        
        coordinates = widget.points_layer.value.data
        sizes = widget.points_layer.value.size
        
        # if widget.img.value.ndim == 2:
            
        #     coordinates = np.pad(sizes, [(0, 0), (1, 0)])
        #     sizes = np.pad(sizes, [(0, 0), (1, 0)])
                                                              
            
        data = np.column_stack((coordinates, sizes))
        
        
        data_df = pd.DataFrame(data, columns=['z_coordinates',
                                              'y_coordinates', 
                                              'x_coordinates',
                                              'size_z',
                                              'size_y',
                                              'size_x'])
    
        min_intensity = []
        max_intensity = []
        mean_intensity = []
        var_intensity = []
        mean_bg_intensity = []
        
        for index, row in data_df.iterrows():
            
            if widget.img.value.ndim == 2:
            
                c_img = widget.img.value.data
                
            else:
                
                c_img = widget.img.value.data[row['z_coordinates'].astype("int"), :, :]
                
            
            rr, cc = disk(tuple(row[1:3]), row['size_y'],
                          shape=np.shape(c_img))
            
            rr_bg, cc_bg = disk(tuple(row[1:3]),
                              2*row['size_y'],
                              shape=np.shape(c_img))
            
            pixels = c_img[rr, cc]
            pixels_bg = c_img[rr_bg, cc_bg]
            
            n_pixels = len(pixels)
            n_pixels_bg = len(pixels_bg)
            
            mean_bg_intensity.append((np.sum(pixels_bg) - np.sum(pixels)) 
                                      / (n_pixels_bg - n_pixels))
            
            mean_intensity.append(np.mean(pixels))
            
            min_intensity.append(np.min(pixels))
            max_intensity.append(np.max(pixels))
            var_intensity.append(np.var(pixels))
        
        ''' Tried to have measurements for spheres for each spot
        but I think that was computationally too expensive'''
        
        # for index, row in data_df.iterrows():
            
        #     sim = nltools.Simulator()
        #     sim.brain_mask = sim.to_nifti(np.ones(widget.img.value.shape, dtype="int"))
        #     sphere = sim.sphere(p=row[0:3], r=row['size_y'])
        #     bg_sphere = sim.sphere(p=row[0:3], r=row['size_y']*2)
            
        #     pixels = widget.img.value[sphere==1]
            
        #     pixels_bg = widget.img.value[bg_sphere==1]
            
        #     n_pixels = len(pixels)
        #     n_pixels_bg = len(pixels_bg)
            
        #     mean_bg_intensity.append((np.sum(pixels_bg) - np.sum(pixels)) 
        #                               / (n_pixels_bg - n_pixels))
            
        #     mean_intensity.append(np.mean(pixels))
            
        #     min_intensity.append(np.min(pixels))
        #     max_intensity.append(np.max(pixels))
        #     var_intensity.append(np.var(pixels))
        
        data_df['min_intensity'] = min_intensity
        data_df['max_intensity'] = max_intensity
        data_df['mean_intensity'] = mean_intensity 
        data_df['var_intensity'] = var_intensity
        data_df['mean_background_intensity'] = mean_bg_intensity
        data_df['SNR'] = np.array(mean_intensity)/np.array(mean_bg_intensity)
        
        
        widget.data_df.value = data_df
        widget.filter_df.value = pd.DataFrame()
        
        widget.result_path.visible = True
        widget.save_results.visible = True
        widget.add_filter.visible = True
        
        
        print("Filter initialized.")
        
    widget.subfilter_counter=0
    @widget.add_filter.changed.connect
    def add_filter(event):
        
        if isinstance(widget.data_df.value, pd.DataFrame):
    
            sf = subfilter()
            sf.label = " " 
            sf.name = "subfilter_%02d" % widget.subfilter_counter
            
            widget.insert(-4, sf)
    
            widget.subfilter_counter += 1
            
            # update min/max threshold
            
            sf.threshold.max = np.max(
                  widget.data_df.value[sf.feature.value.value])
            sf.threshold.min = np.min(
                widget.data_df.value[sf.feature.value.value])
            
            
            @sf.threshold.changed.connect
            def apply_filter(event):
                widget.filter_df.value[sf.name] =  (widget.data_df.value[
                    sf.feature.value.value] >= sf.threshold.value)
                
                widget.filter_df.value.all(axis=1)
                
                data_df = widget.data_df.value
                df_filtered = data_df.loc[widget.filter_df.value.all(axis=1)]
                output = df_filtered[['z_coordinates', 
                                      'y_coordinates', 
                                      'x_coordinates']]
                new_size = df_filtered[['size_z', 'size_y', 'size_x']]
                widget.points_layer.value.data = output
                widget.points_layer.value.size = new_size
                
            @sf.feature.changed.connect
            def update_threshold(event):
                
                # update min/max threshold
            
                sf.threshold.max = np.max(
                      widget.data_df.value[sf.feature.value.value])
                sf.threshold.min = np.min(
                    widget.data_df.value[sf.feature.value.value])
                sf.threshold.value = np.min(
                widget.data_df.value[sf.feature.value.value])
                
            @sf.delete.changed.connect
            def delete_subfilter(event):
                sf.threshold.value = sf.threshold.min
                widget.remove(sf.name)
                
                
        else:
            raise Exception("Filter was not initialized.") 
            
    @widget.save_results.changed.connect
    def save_results(event):
        
        if len(widget.filter_df.value > 0):
            result_df = widget.data_df.value.loc[
                widget.filter_df.value.all(axis=1)]
        else:
            result_df = widget.data_df.value
            
        result_df.to_csv(widget.result_path.value)
        
class Feature(Enum):
    """A set of valid arithmetic operations for image_arithmetic.

    To create nice dropdown menus with magicgui, it's best
    (but not required) to use Enums.  Here we make an Enum
    class for all of the image math operations we want to
    allow.
    """
    z_coordinates = "z_coordinates"
    y_coordinates = "y_coordinates"
    x_coordinates = "x_coordinates"
    min_intensity = "min_intensity"
    max_intensity = "max_intensity"
    mean_intensity = "mean_intensity"
    var_intensity = "var_intensity"
    mean_background_intensity = "mean_background_intensity"
    SNR = "SNR"
    size_z = "size_z"
    size_y = "size_y"
    size_x = "size_x"


@magic_factory(add_filter={"widget_type": "PushButton", 'visible': False},
               layout='vertical',
               result_path={'mode': 'w', 'label': 'save results',
                            'visible': False},
               save_results={'widget_type': 'PushButton', 'visible': False},
               initialize_filter={'widget_type': 'PushButton'},
               widget_init=filter_init)
def filter_widget(img: Image,
                  points_layer: Points,
                  data_df=Image,
                  filter_df=Image,
                  add_filter=0,
                  initialize_filter=0,
                  result_path=Path(),
                  save_results=0) -> LayerDataTuple:
    pass


@magic_factory(auto_call=True,
               threshold={'label': " ", "widget_type": "FloatSlider"},
               delete={"widget_type": "PushButton"},
               layout='horizontal')
def subfilter(feature: Feature,
              threshold=0,
              delete=0) -> LayerDataTuple:
    pass


##############################################################################


# class Filter(FunctionGui):
   
#     def __init__(self):
       
#         super().__init__(Filter.call,
#                          layout="vertical",
#                          param_options={"add_filter": {'widget_type': 'PushButton'}})
        
#         self.filters = 
        
#         @self.add_filter.changed.connect
#         def add_filter(event):
#             subfilter = Subfilter()
#             self.insert(-1, subfilter)
            
#             @subfilter.threshold.changed.connect
#             def test(event):
                
#                 data_df = widget.data_df.value
#                 df_filtered = data_df.loc[
#                 data_df[widget.feature.value.value] >= widget.threshold.value]
            
            
        
        
        
#     def call(img: ImageData,
#              points_layer: Points,
#              add_filter=0,
#              test=0,
#              data_df=Image,
#              filters=Image) -> LayerDataTuple:
#         print("works")
        
        
        
# class Subfilter(FunctionGui):
    
#     def __init__(self):
    
#         super().__init__(Subfilter.call,
#                          auto_call=True,
#                          layout="vertical",
#                          param_options={"threshold": {'widget_type': 'FloatSlider'}})
        
#     def call(feature: Feature,
#              threshold=0,
#              ):
#         pass
    
    
    

##############################################################################
    


@napari_hook_implementation
def napari_experimental_provide_dock_widget():
    # you can return either a single widget, or a sequence of widgets
    return [blob_detection, filter_widget]


