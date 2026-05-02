<?php

declare(strict_types=1);

if (!defined('WP_CLI') || !(bool) constant('WP_CLI') || !class_exists('WP_CLI')) {
    return;
}

use AIWAF\AIWAF;

\WP_CLI::add_command('aiwaf train', static function (array $args, array $assocArgs): void {
    $disableAi = array_key_exists('disable-ai', $assocArgs);
    $forceAi = array_key_exists('force-ai', $assocArgs);

    $waf = new AIWAF();
    $waf->detectAndTrain($disableAi, $forceAi);

    \WP_CLI::success('AIWAF training complete: ' . json_encode(AIWAF::getLastTrainingTelemetry()));
});
