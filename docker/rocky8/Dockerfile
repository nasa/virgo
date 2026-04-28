# Rocky Linux 8 with Python 3.11
FROM rockylinux:8

# Install Python 3.11 from the appstream module
RUN dnf upgrade -y && dnf install -y \
  python3.11 \
  python3.11-pip \
  && dnf clean all

