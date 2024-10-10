# Dockerfile to build the fence-agents locally

Usage is as follows:

```
podman build -f docker/Dockerfile -t fence-agents:main .
podman run -it -v $PWD:/code --rm localhost/fence-agents:main
```

In case you are running docker replace `podman` with `docker` and it should work the same.
