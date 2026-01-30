import time
import functools
from typing import Callable, Any

def cprint(text, color="white", bold=False):
    colors = {
        "red": "\033[91m",
        "green": "\033[92m",
        "yellow": "\033[93m",
        "blue": "\033[94m",
        "white": "\033[97m",
    }
    reset = "\033[0m"
    bold_code = "\033[1m" if bold else ""
    print(f"{bold_code}{colors.get(color, '')}{text}{reset}")


def timed_debug(prefix: str = "", decimals: int = 3) -> Callable:
    """
    Decorator to measure and print wall-clock execution time of a function.
    
    Args:
        prefix: Optional string to prepend to the output message (e.g., function name or context).
        decimals: Number of decimal places to show in the time output.
    
    Returns:
        Decorated function.
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            start_time = time.perf_counter()  # High-resolution wall-clock time
            result = func(*args, **kwargs)
            end_time = time.perf_counter()
            elapsed = (end_time - start_time) * 1000
            
            func_name = func.__name__
            msg_prefix = f"{prefix}: " if prefix else ""
            first_part = f"{msg_prefix}{func_name}"
            print(f"{first_part:<40} took {elapsed:>15.{decimals}f} ms")
            return result
        return wrapper
    return decorator

def time_render_layers(render_window, renderers):
    """
    A debug tool used to measure how long each layer takes to render.
    Note that all layers are forcibly turned on in this function in
    order to time them. In VirgoControlCenter.render() some layers
    may be turned off from actions in configure_renderers()

    renderers: dict of renderers from Virgo.py
    render_window: The render window itself
    """
    # Disable auto-rendering
    render_window.SetDesiredUpdateRate(0)
    # Measure each renderer
    render_times = {}
    
    for layer_name in renderers.keys():
        renderer = renderers[layer_name]
        
        # Temporarily hide other renderers
        for other_name, other_renderer in renderers.items():
            if other_name != layer_name:
                other_renderer.SetDraw(False)
        
        renderer.SetDraw(True)
        
        # Render and measure
        start = time.time()
        render_window.Render()
        elapsed = time.time() - start
        
        render_times[layer_name] = elapsed
        print(f"  DEBUG: {layer_name} takes: {elapsed*1000:.2f} ms to render")
    
    # Re-enable all renderers
    for renderer in renderers.values():
        renderer.SetDraw(True)
    
    # Do a final full render
    render_window.Render()
