FROM docker.sunet.se/eduid/python3env

MAINTAINER eduid-dev <eduid-dev@SEGATE.SUNET.SE>

ADD docker/setup.sh /setup.sh
RUN /setup.sh

ADD docker/start.sh /start.sh

# Add Dockerfile to the container as documentation
ADD Dockerfile /Dockerfile

# revision.txt is dynamically updated by the CI for every build,
# to ensure build.sh is executed every time
ADD docker/revision.txt /revision.txt

ADD docker/build.sh /build.sh
RUN /build.sh

WORKDIR /

EXPOSE 8080

CMD ["bash", "/start.sh"]
