package lab.maidops.lab;

import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

@Component
public class TrainingLeaseSweeper {
    private final TrainingService training;

    public TrainingLeaseSweeper(TrainingService training) {
        this.training = training;
    }

    @Scheduled(fixedDelayString = "${maidops.lease-sweep-ms:5000}")
    public void sweep() {
        training.expireLeases();
    }
}
