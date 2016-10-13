## \file Test_BrainStripping.py
#  \brief  Class containing unit tests for module BrainStripping
# 
#  \author Michael Ebner (michael.ebner.14@ucl.ac.uk)
#  \date December 2015


# Import libraries 
import SimpleITK as sitk
import numpy as np
import unittest
import sys

## Add directories to import modules
dir_src_root = "../src/"
sys.path.append( dir_src_root )
sys.path.append( dir_src_root + "preprocessing/" )
sys.path.append( dir_src_root + "base/" )

## Import modules from src-folder
import SimpleITKHelper as sitkh
import BrainStripping as bs

## Concept of unit testing for python used in here is based on
#  http://pythontesting.net/framework/unittest/unittest-introduction/
#  Retrieved: Aug 6, 2015
class Test_BrainStripping(unittest.TestCase):

    ## Specify input data
    dir_input = "data/"

    accuracy = 7

    def setUp(self):
        pass

    ## Test whether private function _get_zero_framed_stack within FirstEstimateOfHRVolume
    #  works correctly
    def test_01_input_output(self):
        filename = "stack0"

        brain_stripping = bs.BrainStripping.from_filename(self.dir_input, filename)
        brain_stripping.compute_brain_image(0)
        brain_stripping.compute_brain_mask(0)
        brain_stripping.compute_skull_image(0)
        # brain_stripping.set_bet_options("-f 0.3")

        brain_stripping.run_stripping()
        # original_sitk = brain_stripping.get_input_image_sitk()
        # brain_mask_sitk = brain_stripping.get_brain_mask_sitk()
        # brain_sitk = brain_stripping.get_brain_image_sitk()
        # skull_mask_sitk = brain_stripping.get_skull_image_sitk()
        # sitkh.show_sitk_image([original_sitk], segmentation=brain_mask_sitk)

        with self.assertRaises(ValueError) as ve:
            brain_stripping.get_brain_image_sitk()
        self.assertEqual("Brain was not asked for. Do not set option '-n' and run again.", str(ve.exception) )

        with self.assertRaises(ValueError) as ve:
            brain_stripping.get_brain_mask_sitk()
        self.assertEqual("Brain mask was not asked for. Set option '-m' and run again.", str(ve.exception) )

        with self.assertRaises(ValueError) as ve:
            brain_stripping.get_skull_image_sitk()
        self.assertEqual("Skull mask was not asked for. Set option '-s' and run again.", str(ve.exception) )