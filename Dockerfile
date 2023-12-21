FROM nathanpb/dssat-csm

COPY . /app/pythia
RUN apt-get update
RUN apt-get install -y python3 python3-fiona python3-rasterio python3-shapely python3-jinja2
RUN apt-get clean

WORKDIR /app/pythia
ENTRYPOINT ["python3", "-m", "pythia"]
