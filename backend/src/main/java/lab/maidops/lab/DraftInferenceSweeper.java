package lab.maidops.lab;

import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

@Component
public class DraftInferenceSweeper {
    private final ModelDraftService drafts;

    public DraftInferenceSweeper(ModelDraftService drafts) {
        this.drafts = drafts;
    }

    @Scheduled(fixedDelayString = "${maidops.lease-sweep-ms:5000}")
    public void sweep() {
        drafts.expireLeases();
    }
}
