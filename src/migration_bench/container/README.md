## Container


### EC2

To build and launch the container on your machine (EC2):

```
cd .../container
./image.sh self-dbg sliuxl  # 1 docker/Dockerfile
./launch.sh  # sliuxl__self-dbg
```

For Java only, you can also use:

```
cd .../container
./image.sh java $USER 1 docker/java.Dockerfile 992382830173.dkr.ecr.us-west-2.amazonaws.com
./launch.sh  # sliuxl__self-dbg
```

#### Debug
When `./image.sh ...` has errors,
it'd be helpful to go to `./docker` directory,
and build it there following the commands in `./docker/Dockerfile` at the top.

- This way it has more error information available.
