FROM php:8.1-cli

WORKDIR /workspace
COPY . /workspace

RUN apt-get update \
  && apt-get install -y --no-install-recommends git unzip libzip-dev \
  && docker-php-ext-install zip \
  && rm -rf /var/lib/apt/lists/*

COPY --from=composer:2 /usr/bin/composer /usr/bin/composer
RUN cd /workspace/examples && composer install --no-dev --no-interaction --prefer-dist --no-progress \
  && php /workspace/examples/vendor/aayushgauba/aiwaf/setup.php

CMD ["php", "-S", "0.0.0.0:8081", "examples/sandbox/aiwaf-laravel/router.php"]
