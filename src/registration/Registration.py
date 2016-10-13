#!/usr/bin/python

## \file Registration.py
#  \brief 
#
#  \author Michael Ebner (michael.ebner.14@ucl.ac.uk)
#  \date Aug 2016


## Import libraries
import sys
import itk
import SimpleITK as sitk
import numpy as np
from scipy.optimize import least_squares
import time

## Add directories to import modules
DIR_SRC_ROOT = "../../src/"
sys.path.append(DIR_SRC_ROOT + "base/")

## Import modules
import SimpleITKHelper as sitkh
import PSF as psf
import Slice as sl
import time
from datetime import timedelta

## Pixel type of used 3D ITK image
PIXEL_TYPE = itk.D

## ITK image type
IMAGE_TYPE = itk.Image[PIXEL_TYPE, 3]
IMAGE_TYPE_CV33 = itk.Image.CVD33
IMAGE_TYPE_CV183 = itk.Image.CVD183


##-----------------------------------------------------------------------------
# \brief      Class for registration in 3D based on least-squares optimization
# \date       2016-09-21 12:27:13+0100
#
class Registration(object):

    #--------------------------------------------------------------------------
    # \brief      Constructor
    # \date       2016-08-02 15:49:34+0100
    #
    # \param[in]  self       The object
    # \param[in]  fixed      Fixed image as Stack or Slice object (S2VReg:
    #                        Slice)
    # \param[in]  moving     Moving image as Stack or Slice object (S2VReg: HR
    #                        Volume)
    # \param[in]  alpha_cut  The alpha cut
    # \param[in]  verbose    The verbose
    #
    def __init__(self, fixed=None, moving=None, use_fixed_mask=False, alpha_cut=3, use_verbose=False):

        self._fixed = fixed
        self._moving = moving

        self._use_fixed_mask = use_fixed_mask

        self._alpha_cut = alpha_cut

        ## Used for PSF modelling
        self._psf = psf.PSF()

        ## Create PyBuffer object for conversion between NumPy arrays and ITK images
        self._itk2np = itk.PyBuffer[IMAGE_TYPE]
        self._itk2np_CVD33 = itk.PyBuffer[IMAGE_TYPE_CV33]
        self._itk2np_CVD183 = itk.PyBuffer[IMAGE_TYPE_CV183]

        ## Create transform instances
        self._rigid_transform_itk = itk.Euler3DTransform[PIXEL_TYPE].New()
        self._parameters_itk = self._rigid_transform_itk.GetParameters()
        self._dof_transform = self._rigid_transform_itk.GetNumberOfParameters()
        self._parameters = [None]*self._dof_transform

        ## Verbose computation
        self._use_verbose = use_verbose


    ##-------------------------------------------------------------------------
    # \brief      Initialize registration class
    # \date       2016-09-21 12:58:57+0100
    #
    # Idea: Have same structure as other registration classes and add moving
    # and fixed images later on via set routines. Several filters need to be
    # initialized according to the updates
    #
    # \param      self  The object
    #
    def _initialize_class(self):

        ## Properties of fixed
        self._fixed_affine_transform_sitk = sitkh.get_sitk_affine_transform_from_sitk_image(self._fixed.sitk)
        self._fixed_spacing = self._fixed.sitk.GetSpacing()
        self._fixed_size = self._fixed.sitk.GetSize()
        self._fixed_voxels = np.array(self._fixed_size).prod()

        ## Allocate and initialize Oriented Gaussian Interpolate Image Filter
        self._filter_oriented_Gaussian = itk.OrientedGaussianInterpolateImageFilter[IMAGE_TYPE, IMAGE_TYPE].New()
        self._filter_oriented_Gaussian.SetDefaultPixelValue(0.0)
        self._filter_oriented_Gaussian.SetAlpha(self._alpha_cut)
        self._filter_oriented_Gaussian.SetInput(self._moving.itk)
        self._filter_oriented_Gaussian.SetUseJacobian(False)
        self._filter_oriented_Gaussian.SetUseImageDirection(True)

        ## Allocate and initialize Adjoint Oriented Gaussian Interpolate Image Filter
        self._filter_adjoint_oriented_Gaussian = itk.AdjointOrientedGaussianInterpolateImageFilter[IMAGE_TYPE, IMAGE_TYPE].New()
        self._filter_adjoint_oriented_Gaussian.SetDefaultPixelValue(0.0)
        self._filter_adjoint_oriented_Gaussian.SetAlpha(self._alpha_cut)
        self._filter_adjoint_oriented_Gaussian.SetOutputParametersFromImage(self._moving.itk)

        ## Allocate and initialize Gradient Euler3DTransform Image Filter
        self._filter_gradient_transform = itk.GradientEuler3DTransformImageFilter[IMAGE_TYPE, PIXEL_TYPE, PIXEL_TYPE].New()
        self._filter_gradient_transform.SetInput(self._fixed.itk)
        self._filter_gradient_transform.SetTransform(self._rigid_transform_itk)

        if self._use_fixed_mask:
            # self._nda_mask = sitk.GetArrayFromImage(self._fixed.sitk_mask).reshape(-1,1)
            self._nda_mask = sitk.GetArrayFromImage(self._fixed.sitk_mask).flatten()

    ## Set fixed/reference/target image
    #  \param[in] fixed fixed/reference/target image as Stack object
    def set_fixed(self, fixed):
        self._fixed = fixed


    ## Set moving/floating/source image
    #  \param[in] moving moving/floating/source image as Stack object
    def set_moving(self, moving):
        self._moving = moving


    ## Specify whether mask shall be used for fixed image
    #  \param[in] flag boolean
    def use_fixed_mask(self, flag):
        self._use_fixed_mask = flag


    # ## Specify whether mask shall be used for moving image
    # #  \param[in] flag boolean
    # def use_moving_mask(self, flag):
    #     self._use_moving_mask = flag


    ## Set cut-off distance
    #  \param[in] alpha_cut scalar value
    def set_alpha_cut(self, alpha_cut):
        self._alpha_cut = alpha_cut


    ## Get cut-off distance
    #  \return scalar value
    def get_alpha_cut(self):
        return self._alpha_cut


    ##-------------------------------------------------------------------------
    # \brief      Gets the parameters estimated by registration algorithm.
    # \date       2016-08-03 00:10:45+0100
    #
    # \param[in]  self  The object
    #
    # \return     The parameters.
    #
    def get_parameters(self):
        return self._parameters


    ##-------------------------------------------------------------------------
    # \brief      Returns the rigid registration transform
    # \date       2016-09-21 12:09:41+0100
    #
    # \param      self  The object
    #
    # \return     The registration transform as sitk.Euler3DTransform object.
    #
    def get_registration_transform_sitk(self):
        transform_sitk = sitk.Euler3DTransform()
        transform_sitk.SetParameters(self._parameters)
        return transform_sitk


    ##-------------------------------------------------------------------------
    # \brief      Sets the verbose to define whether or not output is produced
    # \date       2016-09-20 18:49:19+0100
    #
    # \param      self     The object
    # \param      verbose  The verbose
    #
    def use_verbose(self, flag):
        self._use_verbose = flag

    
    ##-------------------------------------------------------------------------
    # \brief      Gets the verbose.
    # \date       2016-09-20 18:49:54+0100
    #
    # \param      self  The object
    #
    # \return     The verbose.
    #
    def get_verbose(self):
        return self._use_verbose


    ##-------------------------------------------------------------------------
    # \date       2016-07-29 12:30:30+0100
    # \brief      Print statistics associated to performed reconstruction
    #
    # \param[in]  self  The object
    #
    def print_statistics(self):
        # print("\nStatistics for performed registration:" %(self._reg_type))
        # if self._elapsed_time_sec < 0:
        #     raise ValueError("Error: Elapsed time has not been measured. Run 'run_reconstruction' first.")
        # else:
        print("\tElapsed time = %s" %(timedelta(seconds=self._elapsed_time_sec)))
        # print("\tell^2-residual sum_k ||M_k(A_k x - y_k||_2^2 = %.3e" %(self._residual_ell2))
        # print("\tprior residual = %.3e" %(self._residual_prior))


    ##-------------------------------------------------------------------------
    # \brief      Run registration
    # \date       2016-08-03 00:11:51+0100
    # \post       self._paramters is updated
    #
    # \param[in]  self     The object
    #
    def run_registration(self):
        
        ## 
        self._initialize_class()

        ## Define type of verbose (available at least_squares)
        if self._use_verbose:
            verbose = 2
        else:
            verbose = 0

        ## Define variables for least-squares optimization        
        fun = lambda x: self._get_residual_data_fit(x)
        jac = lambda x: self._get_jacobian_residual_data_fit(x)
        x0 = np.zeros(self._dof_transform)

        ## Time optimization
        time_start = time.time()

        ## Non-linear least-squares method:
        # res = least_squares(fun=fun, x0=x0, method='trf', verbose=verbose) 
        res = least_squares(fun=fun, x0=x0, jac=jac, method='trf', loss='linear',verbose=verbose) 
        # res = least_squares(fun=fun, x0=x0, jac='2-point', method='trf', verbose=verbose) 
        # res = least_squares(fun=fun, x0=x0, method='lm', loss='linear', tr_solver='exact', verbose=1) 
        self._parameters = res.x
        
        ## Set elapsed time
        time_end = time.time()
        self._elapsed_time_sec = time_end-time_start


    ##-------------------------------------------------------------------------
    # \brief      Compute residual y_k - A_k(theta)x based on parameters
    #             (theta). 
    # \date       2016-08-03 00:12:43+0100
    #
    # \param[in]  self        The object
    # \param[in]  parameters  The parameters
    #
    # \return     The residual data fit as Nk-array and its Jacobian as (Nk x 6)-array
    #
    def _get_residual_data_fit(self, parameters):

        Ak_vol_itk = self._execute_oriented_gaussian_interpolate_image_filter(parameters, use_jacobian=False)

        nda_fixed = sitk.GetArrayFromImage(self._fixed.sitk)
        nda_Ak_vol = self._itk2np.GetArrayFromImage(Ak_vol_itk)
        residual = (nda_fixed - nda_Ak_vol).flatten()

        if self._use_fixed_mask:
            residual = residual*self._nda_mask

        return residual


    ##-------------------------------------------------------------------------
    # \brief      Gets the jacobian residual data fit.
    # \date       2016-09-08 12:11:13+0100
    #
    # \param[in]  self                         The object
    # \param[in]  parameters                   The parameters
    #
    # \return     The Jacobian residual data fit as (Nk x 6)-array
    #
    def _get_jacobian_residual_data_fit(self, parameters):

        ## Allocate array for Jacobian of residual
        jacobian_nda = np.zeros((self._fixed_voxels, self._dof_transform))

        ## Get Jacobian of filtered image w.r.t. spatial coordinates
        jacobian_spatial_Ak_vol_itk = self._execute_oriented_gaussian_interpolate_image_filter(parameters, use_jacobian=True)

        ## Get array of Jacobian of forward operator w.r.t. spatial coordinates
        nda_gradient_filter = self._itk2np_CVD33.GetArrayFromImage(jacobian_spatial_Ak_vol_itk)
        nda_gradient_filter_vec = nda_gradient_filter.reshape(-1,3)

        ## Get array of Jacobian of transform w.r.t. parameters
        for i in range(0, self._dof_transform):
            self._parameters_itk.SetElement(i,parameters[i])

        self._rigid_transform_itk.SetParameters(self._parameters_itk)
        self._filter_gradient_transform.Update()
        gradient_transform_itk = self._filter_gradient_transform.GetOutput()
        gradient_transform_itk.DisconnectPipeline()

        nda_gradient_transform = self._itk2np_CVD183.GetArrayFromImage(gradient_transform_itk).reshape(-1,3,self._dof_transform)

        ## Compute Jacobian of residual w.r.t. to parameters
        for i in range(0, self._fixed_voxels):
            jacobian_nda[i,:] = nda_gradient_filter_vec[i,:].dot(nda_gradient_transform[i,:,:])

        if self._use_fixed_mask:
        ## https://mail.scipy.org/pipermail/numpy-discussion/2007-March/026506.html
            jacobian_nda = jacobian_nda*self._nda_mask[:,np.newaxis]

        return -jacobian_nda

    
    ##-------------------------------------------------------------------------
    # \brief      Execute Oriented Gaussian Interpolate Image Filter
    # \date       2016-09-20 18:32:12+0100
    #
    # \param[in]  self          The object
    # \param[in]  parameters    The parameters
    # \param[in]  use_jacobian  Boolean to indicate whether Jacobian or the
    #                           filtered image itself is returned
    #
    # \return     Either return filtered image or Jacobian w.r.t to spatial
    #             coordinates of filtered image
    #
    def _execute_oriented_gaussian_interpolate_image_filter(self, parameters, use_jacobian):

        ## Create registration transform based on parameters
        transform_sitk = sitk.Euler3DTransform()
        transform_sitk.SetParameters(parameters)

        ## Get composite affine transform: reg_trafo \circ fixed_space
        composite_transform_sitk = sitkh.get_composite_sitk_affine_transform(transform_sitk, self._fixed_affine_transform_sitk)

        ## Extract direction and origin of transformed fixed space
        direction_sitk = sitkh.get_sitk_image_direction_from_sitk_affine_transform(composite_transform_sitk, self._fixed_spacing)
        origin_sitk = sitkh.get_sitk_image_origin_from_sitk_affine_transform(composite_transform_sitk)

        ## Set output to transformed fixed space
        self._filter_oriented_Gaussian.SetOutputOrigin(origin_sitk)
        self._filter_oriented_Gaussian.SetOutputSpacing(self._fixed_spacing)
        self._filter_oriented_Gaussian.SetOutputDirection(sitkh.get_itk_direction_form_sitk_direction(direction_sitk))
        self._filter_oriented_Gaussian.SetSize(self._fixed_size)
        self._filter_oriented_Gaussian.SetUseJacobian(use_jacobian)
        self._filter_oriented_Gaussian.UpdateLargestPossibleRegion()

        ## Set oriented PSF based on transformed fixed space
        Cov_HR_coord = self._psf.get_gaussian_PSF_covariance_matrix_HR_volume_coordinates_from_direction_and_spacing(direction_sitk, self._fixed_spacing, self._moving)
        self._filter_oriented_Gaussian.SetCovariance(Cov_HR_coord.flatten())

        ## Compute simulated fixed from volume and its Jacobian w.r.t. to spatial coordinates
        self._filter_oriented_Gaussian.Update()
    
        ## 1) Compute residual y_k - A_k(theta)x as 1D array
        if not use_jacobian:
            Ak_vol_itk = self._filter_oriented_Gaussian.GetOutput()
            Ak_vol_itk.DisconnectPipeline()

            return Ak_vol_itk

        ## 2) Compute gradient of residual w.r.t. to spatial coordinates
        else:
            jacobian_spatial_Ak_vol_itk = self._filter_oriented_Gaussian.GetJacobian()
            jacobian_spatial_Ak_vol_itk.DisconnectPipeline()
            
            return jacobian_spatial_Ak_vol_itk


    ##-------------------------------------------------------------------------
    # \brief      Compute squared ell^2 norm of residual, i.e. compute residual
    #             of data fit \f$ \Vert \vec{y}_k - A_k(\theta)\vec{x} \f$
    # \date       2016-08-03 00:43:29+0100
    #
    # \param[in]  self        The object
    # \param[in]  parameters  The parameters containing 6 DOF for rigid trafo
    #
    # \return     ell^2-residual of data fit.
    #
    def _get_residual_ell2(self, parameters):

        ## Get y_k - A_k(theta)x as 1D array
        residual_data_fit = self._get_residual_data_fit(parameters)

        return np.sum(residual_data_fit**2)
     




