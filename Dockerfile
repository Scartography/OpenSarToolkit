ARG BASE_CONTAINER=jupyter/scipy-notebook:7a3e968dd212
FROM $BASE_CONTAINER

USER root

ENV OTB_VERSION="7.0.0" \
    TBX_VERSION="7" \
    TBX_SUBVERSION="0"
ENV TBX="esa-snap_sentinel_unix_${TBX_VERSION}_${TBX_SUBVERSION}.sh" \
  SNAP_URL="http://step.esa.int/downloads/${TBX_VERSION}.${TBX_SUBVERSION}/installers" \
  OTB=OTB-${OTB_VERSION}-Linux64.run \
  HOME=$HOME \
  PATH=$PATH:$HOME/programs/snap/bin:$HOME/programs/OTB-${OTB_VERSION}-Linux64/bin

RUN sed -i -e 's:(groups):(groups 2>/dev/null):' /etc/bash.bashrc && \
    mkdir $HOME/programs

USER $NB_UID
ENV HOME=/home/$NB_USER

# install gdal
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -yq libgdal-dev \
    python3-gdal \
    libspatialindex-dev \
    libgfortran3 && \
    rm -rf /var/lib/apt/lists/*  && \
    alias python=python3

RUN jupyter labextension install @jupyterlab/geojson-extension

# copy the snap installation config file into the container
COPY snap7.varfile $HOME/programs/

# Download and install SNAP and ORFEO Toolbox
RUN cd  $HOME/programs && \
    wget $SNAP_URL/$TBX && \
    chmod +x $TBX && \
    ./$TBX -q -varfile snap7.varfile && \
    rm $TBX && \
    rm snap7.varfile && \
    cd $HOME/programs && \
    wget https://www.orfeo-toolbox.org/packages/${OTB} && \
    chmod +x $OTB && \
    ./${OTB} && \
    rm -f OTB-${OTB_VERSION}-Linux64.run

# get OST and tutorials
RUN cd $HOME && \
    git clone https://github.com/Scartography/OpenSarToolkit.git && \
    cd $HOME/OpenSarToolkit && \
    pip install setuptools && \
    git checkout timeseries_tests && \
    pip install -r requirements.txt && \
    pip install -r requirements_test.txt && \
    python setup.py install && \
    cd $HOME && \
    git clone https://github.com/Scartography/OST_Notebooks.git && \
    cd $HOME/OST_Notebooks && \
    git checkout SLC_processing

USER root
RUN fix-permissions $HOME
USER $NB_UID

# setup jupyter hub and expose the environment
EXPOSE 8888
RUN cd $HOME
CMD jupyter lab --ip='0.0.0.0' --port=8888 --no-browser --allow-root
