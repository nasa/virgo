DOCKER_RELEASE_TAG=0.1
HERE  := $(dir $(realpath $(firstword $(MAKEFILE_LIST))))
VIRGO_ROOT  := $(realpath ${HERE}/..)
UNAME := $(shell uname)
MYUID := $(shell id -u ${USER} )
MYGID := $(shell id -g ${USER} )
MYNAME := $(shell whoami)
HOSTNAME := $(shell hostname -f)
USER_HOME_DIR=${HOME}
GITLAB_AUTH_FILE=${HOME}/.luna-gitlab-auth.json
# docker can be used instead of docker by running make TOOL=docker <target>
TOOL=podman
REGISTRY=registry.code.luna.nasa.gov/daniel-jordan/virgo
OS_PREFIX=r8
IMAGE=$(REGISTRY)/$(OS_PREFIX)-$(DOCKER_RELEASE_TAG)
CMD='' # Used for batch execution, defaults to empty


.PHONY: build build-rocky8 run

all: run

clean:
	rm .build-rocky8

# Rule for building the base image
build-rocky8:
	$(TOOL) build --platform linux/amd64 -t $(IMAGE) -f rocky8/Dockerfile .

COMMON_RUN_ARGS := -ti \
      --rm \
      --platform linux/amd64 \
      --authfile=$(GITLAB_AUTH_FILE) \
      -e HOME=${USER_HOME_DIR} \
      -v "${USER_HOME_DIR}:${USER_HOME_DIR}/" \
      -v "${VIRGO_ROOT}:${VIRGO_ROOT}" 

run:
	@$(TOOL) run  \
	  $(COMMON_RUN_ARGS) \
      $(IMAGE)

$(GITLAB_AUTH_FILE):
	$(TOOL) login --authfile=$(GITLAB_AUTH_FILE) -u $(USER) --tls-verify=false $(REGISTRY)
	chmod go-rwx $@  # Make sure only user has access

login: .login-$(HOSTNAME)
.login-$(HOSTNAME): | $(GITLAB_AUTH_FILE)
	touch $@



.PHONY: all

help:
	##########################################################################
	#               VIRGO Container Configuration Makefile
	# Use 'make <target> TOOL=docker|podman' to change tool (default: ${TOOL})
	##########################################################################
	# Target              Action
	##########################################################################
	# help                Display this message
	# build-rocky8        Build Rocky 8.X container for local use.
	#                     This image includes the base image and adds user-
	#                     specific customizations to allow local development
	#                     inside the container. Output goes to .build-rocky8
	# run                 Run latest container for local use
	# push-base           Execute '$(TOOL) login' and '$(TOOL) push' for the
	#                     local image built by build-rocky8-base. Use this
	#                     to update the registry with a newly built version
	# login               Authenticate with GitLab Project Registry. Use your
	#                     GitLab username and Personal Access Token (PAT) for
	#                     password when prompted
