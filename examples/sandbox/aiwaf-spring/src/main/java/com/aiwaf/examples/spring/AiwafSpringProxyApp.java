package com.aiwaf.examples.spring;

import com.aiwaf.core.AiwafConfig;
import com.aiwaf.core.AiwafEngine;
import com.aiwaf.spring.AiwafFilter;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.web.servlet.FilterRegistrationBean;
import org.springframework.context.annotation.Bean;

@SpringBootApplication
public class AiwafSpringProxyApp {
    public static void main(String[] args) {
        SpringApplication.run(AiwafSpringProxyApp.class, args);
    }

    @Bean
    AiwafEngine aiwafEngine() {
        AiwafConfig config = new AiwafConfig();
        config.geoBlockEnabled = false;
        config.rateLimitEnabled = true;
        config.rateLimitWindowSeconds = 10;
        config.rateLimitMax = 20;
        config.rateLimitFloodThreshold = 40;
        config.honeypotEnabled = true;
        config.uuidTamperEnabled = true;
        config.ipKeywordBlockEnabled = true;
        return new AiwafEngine(config);
    }

    @Bean
    FilterRegistrationBean<AiwafFilter> aiwafFilterRegistration(AiwafEngine engine) {
        FilterRegistrationBean<AiwafFilter> bean = new FilterRegistrationBean<>();
        bean.setFilter(new AiwafFilter(engine));
        bean.addUrlPatterns("/*");
        bean.setOrder(1);
        return bean;
    }
}
