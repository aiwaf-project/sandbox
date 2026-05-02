<?php

declare(strict_types=1);

namespace App\Command;

use AIWAF\AIWAF;
use Symfony\Component\Console\Attribute\AsCommand;
use Symfony\Component\Console\Command\Command;
use Symfony\Component\Console\Input\InputInterface;
use Symfony\Component\Console\Input\InputOption;
use Symfony\Component\Console\Output\OutputInterface;

#[AsCommand(name: 'aiwaf:train', description: 'Run AIWAF log trainer')]
final class TrainAiWafCommand extends Command
{
    protected function configure(): void
    {
        $this
            ->addOption('force-ai', null, InputOption::VALUE_NONE)
            ->addOption('disable-ai', null, InputOption::VALUE_NONE);
    }

    protected function execute(InputInterface $input, OutputInterface $output): int
    {
        $waf = new AIWAF();
        $waf->detectAndTrain((bool) $input->getOption('disable-ai'), (bool) $input->getOption('force-ai'));

        $output->writeln('AIWAF training complete: ' . json_encode(AIWAF::getLastTrainingTelemetry()));

        return Command::SUCCESS;
    }
}
