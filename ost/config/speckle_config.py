
SPECKLE_FILTERS = ['None', 'Boxcar', 'Median', 'Frost', 'Gamma Map',
                   'Lee', 'Refined Lee', 'Lee Sigma', 'IDAN'
                   ]
SIGMA_LEE = [0.5, 0.6, 0.7, 0.8, 0.9]
WINDOW_SIZES = ['3x3', '5x5']
TARGET_WINDOW_SIZES = ['5x5', '7x7', '9x9', '11x11', '13x13', '15x15', '17x17']

DEFAULT_MT_SPECKLE_DICT = {
    "filter": "Refined Lee",
    "ENL": 1.0,
    "estimate_ENL": True,
    "sigma": 0.9,
    "filter_x_size": 3,
    "filter_y_size": 3,
    "window_size": "7x7",
    "target_window_size": "3x3",
    "num_of_looks": 1,
    "damping": 2,
    "pan_size": 50
}
