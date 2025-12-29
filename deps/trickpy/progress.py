import time
import sys
import subprocess

class ProgressBar:
    """A progress bar shown in the terminal."""

    def __init__(self, description, final_count):
        self.description = description
        self.final_count = final_count
        self.count_digits = len(str(final_count))
        self.refresh = 1.0
        self.last_time = time.time()

        p = subprocess.Popen(["stty", "size"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = p.communicate()
        if p.returncode == 0:
            self.tty_width = int(stdout.split()[1])
        else:
            self.tty_width = 50

    def show(self, count):
        """Show the progress bar with *count* completed items."""
        now = time.time()
        if now > self.last_time + self.refresh or count == 0:
            self.last_time = now
            head = self.description + " ["
            tail = "] {{:{}}} / {{:{}}}".format(self.count_digits, self.count_digits).format(count, self.final_count)
            bar_final_size = self.tty_width - len(head) - len(tail) - 1
            bar_percent = float(count) / self.final_count
            bar_current_size = max(1, int(bar_final_size * bar_percent))
            bar = "-" * (bar_current_size-1) + ">" + " " * (bar_final_size - bar_current_size)
            sys.stderr.write("\r{}{}{}".format(head, bar, tail))
            sys.stderr.flush()

    def clear(self):
        """Clear the progress bar from the terminal."""
        sys.stderr.write("\r{}\r".format(" " * self.tty_width))
