package lab.maidops.worker;

import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

@Component
public class LeaseSweeper {
    private final WorkerJobService workers;

    public LeaseSweeper(WorkerJobService workers) {
        this.workers = workers;
    }

    @Scheduled(fixedDelayString = "${maidops.lease-sweep-ms:5000}")
    public void sweep() {
        workers.expireLeases();
    }
}
