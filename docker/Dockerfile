FROM opensuse/leap:15.5

RUN zypper in -y \
    git \
    autoconf \
    automake \
    libtool \
    make \
    gcc \
    libcorosync-devel \
    libxslt1 \
    libxslt-tools \
    python3-devel \
    python3-httplib2 \
    python3-pexpect \
    python3-pycurl \
    python3-requests \
    python3-suds-jurko \
    python3-openwsman \
    python3-boto3 \
    python3-novaclient \
    python3-keystoneclient \
    mozilla-nss-devel \
    mozilla-nspr-devel \
    libvirt-devel \
    libxml2-devel \
    flex \
    bison \
    libuuid-devel \
    systemd

WORKDIR /code
VOLUME /code
ENTRYPOINT ["./docker/entrypoint.sh"]
