package com.aiwaf.examples.spring;

import com.aiwaf.core.AiwafConfig;
import com.aiwaf.spring.SpringAiwafConfig;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.Bean;
import org.springframework.core.env.Environment;

import java.util.Arrays;

@SpringBootApplication
public class AiwafSpringProxyApp {
    public static void main(String[] args) {
        SpringApplication.run(AiwafSpringProxyApp.class, args);
    }

    @Bean
    AiwafConfig aiwafConfig(Environment environment) {
        AiwafConfig config = SpringAiwafConfig.fromEnvironment(environment);
        // The attack runner simulates clients through Docker's bridge gateway.
        Arrays.stream(environment.getProperty("sandbox.trusted-proxy-cidrs", "172.16.0.0/12").split(","))
                .map(String::trim).filter(value -> !value.isEmpty()).forEach(config.trustedProxyCidrs::add);
        return config;
    }
}
