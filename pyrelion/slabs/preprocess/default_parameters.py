def get_config():
    """
    Returns a configuration dictionary for class2D and select process.
    """
    return {
        "class2D": {
            "do_zero_mask": "yes",
            "psi_sampling": 6,
            "offset_range": 5,
            "offset_step": 1,
            "allow_coarser": "no",
            "nr_pool": 30,
            "do_preread_images": "no",
            "gpu_ids": "",
        },
        "select": {
            "do_select_values": "yes",
            "select_label": "rlnClassNumber"
        }
    }
