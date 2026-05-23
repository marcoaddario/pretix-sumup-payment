FROM --platform=linux/amd64 pretix/standalone:stable

USER root

RUN pip install --no-cache-dir watchdog

RUN rm -f /etc/supervisord/pretixtask.conf

WORKDIR /pretix/src

COPY . /pretix/plugins/pretix-sumup-payment
RUN pip install -e /pretix/plugins/pretix-sumup-payment

ENV PRETIX_DEBUG=1 \
    PYTHONUNBUFFERED=1 \
    NUM_WORKERS=1
