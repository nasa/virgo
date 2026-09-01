# Camera Frustum Example

This example shows how to configure camera frustum visualization in a YAML scene file. Each user-facing camera can draw its field of view as a wireframe pyramid in the scene.

## Files

* `camera_frustum.py` — loads `scene.yml` and opens the interactive VIRGO window
* `scene.yml` — scene with three cameras and frustum settings

## Running

```bash
./camera_frustum.py
```

## What to look for

The scene places a large blue **target** cube at the origin with two smaller marker cubes nearby. Three cameras are defined:

| Camera | Role | Frustum color |
|--------|------|---------------|
| `default` | Trackball overview (starting view) | None |
| `side_view` | Fixed camera on the −X side | Pink |
| `top_view` | Fixed camera from above | Green |
| `third_camera_view` | Fixed camera from close to `default`'s starting point | Yellow |

Colored **frame axes** mark where the side and top cameras sit (`side_cam_frame`, `top_cam_frame` in `scene.yml`).

Press **Up/Down** to switch cameras and **f** to toggle frustum visibility. The **inactive** cameras show their frustums; the **active** camera hides its own frustum so it does not block the view.

Press **L** to toggle labels and find the target cube.

## YAML frustum options

Add these keys under any entry in `cameras:`:

```yaml
cameras:
  my_camera:
    pos: [5.0, 0.0, 2.0]
    focal_point: [0.0, 0.0, 0.0]
    frustum_when: always      # always | never | toggled (default: toggled)
    frustum_far_plane: 10.0   # depth of the pyramid in scene units
    frustum_color: [1.0, 0.9, 0.1]
```

* `frustum_when: always` — draw the frustum whenever this camera is not the active view
* `frustum_when: never` — no frustum geometry (default for internal layer cameras)
* `frustum_when: toggled` — draw the frustum when toggled with 'f'
* `frustum_far_plane` — how far the pyramid extends along the view axis
* `frustum_color` — RGB wireframe color, each component 0.0–1.0. Defaults to [1.0, 1.0, 1.0]

Static cameras with explicit `focal_point:` (see `side_view` and `top_view`) are a straightforward way to aim a frustum at a scene feature. First-person cameras parented to a `frames:` entry are also supported — see `examples/hello_cube/`.
