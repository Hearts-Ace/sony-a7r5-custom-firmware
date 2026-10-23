import unittest
import numpy as np
import core
import measured_response
from photo_backend import enable

class PhotoBackendTests(unittest.TestCase):
    def test_exact_forward_and_grid_prediction(self):
        response=measured_response.default_response()
        model=measured_response.get(response)
        rng=np.random.default_rng(7)
        rgb=np.r_[rng.random((2200,3)),np.zeros((1,3)),np.ones((1,3))]
        table=rng.integers(-20,21,(405,3))
        before=model.predict(rgb,table)
        coordinates=model.coordinates(rgb)
        derivative=model.forward(coordinates[:10],True)
        enable(response)
        np.testing.assert_allclose(model.predict(rgb,table),before,rtol=0,atol=1e-12)
        np.testing.assert_array_equal(model.forward(coordinates[:10],True),derivative)
        self.assertEqual(model.forward(np.empty((0,3))).shape,(0,3))

if __name__=='__main__':unittest.main()
