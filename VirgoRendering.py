class VirgoRendering:
    internal_layers = ['skybox', 'sun',]
    user_facing_layers = ['background', 'midground', 'foreground']
    # Cameras that sync to foreground camera
    cameras_to_sync = ['background', 'midground', 'sun', 'skybox']
    non_user_facing_cameras = internal_layers + user_facing_layers

