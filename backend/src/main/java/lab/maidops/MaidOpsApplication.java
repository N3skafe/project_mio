package lab.maidops;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.CommandLineRunner;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.core.env.Environment;
import org.springframework.scheduling.annotation.EnableScheduling;
import org.springframework.stereotype.Component;

@SpringBootApplication
@EnableScheduling
public class MaidOpsApplication {
    public static void main(String[] args) {
        SpringApplication.run(MaidOpsApplication.class, args);
    }

    @Component
    static class StartupNotice implements CommandLineRunner {
        private static final Logger log = LoggerFactory.getLogger(StartupNotice.class);
        private final Environment environment;

        StartupNotice(Environment environment) {
            this.environment = environment;
        }

        @Override
        public void run(String... args) {
            String address = environment.getProperty("server.address", "127.0.0.1");
            String port = environment.getProperty("server.port", "8080");
            log.warn("인증이 없습니다. localhost 단일 사용자용입니다. 외부 네트워크에 노출하지 마세요. bind={}:{}", address, port);
            log.info("등록된 argv만 워커가 실행합니다. 워커가 없으면 작업은 QUEUED로 남습니다.");
        }
    }
}
