FROM php:8.4-cli

WORKDIR /workspace
COPY . /workspace

RUN apt-get update \
  && apt-get install -y --no-install-recommends git unzip libzip-dev \
  && docker-php-ext-install zip \
  && rm -rf /var/lib/apt/lists/*

COPY --from=composer:2 /usr/bin/composer /usr/bin/composer
RUN cd /workspace/examples && composer install --no-interaction --prefer-dist --no-progress

CMD ["./vendor/bin/phpunit", "--colors=never", "--do-not-cache-result"]
