package lab.maidops.lab;

import jakarta.validation.Valid;
import lab.maidops.lab.LabPayloads.ClaimedTraining;
import lab.maidops.lab.LabPayloads.CompleteTrainingRequest;
import lab.maidops.lab.LabPayloads.ExampleList;
import lab.maidops.lab.LabPayloads.FailTrainingRequest;
import lab.maidops.lab.ModelDraftService.ClaimedInference;
import lab.maidops.lab.ModelDraftService.CompleteInferenceRequest;
import lab.maidops.lab.LabPayloads.HeartbeatResponse;
import lab.maidops.lab.LabPayloads.ModelVersionResponse;
import lab.maidops.lab.LabPayloads.TrainingRunResponse;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/trainer")
public class TrainerController {
    private final TrainingService training;
    private final ModelDraftService drafts;

    public TrainerController(TrainingService training, ModelDraftService drafts) {
        this.training = training;
        this.drafts = drafts;
    }

    @PostMapping("/claim")
    public ResponseEntity<ClaimedTraining> claim(@RequestHeader("X-Trainer-Id") String trainerId) {
        return training.claim(trainerId)
                .map(ResponseEntity::ok)
                .orElseGet(() -> ResponseEntity.noContent().build());
    }

    @GetMapping("/runs/{id}/examples")
    public ExampleList examples(
            @RequestHeader("X-Trainer-Id") String trainerId,
            @PathVariable String id) {
        return training.examples(trainerId, id);
    }

    @PostMapping("/runs/{id}/heartbeat")
    public HeartbeatResponse heartbeat(
            @RequestHeader("X-Trainer-Id") String trainerId,
            @PathVariable String id) {
        return training.heartbeat(trainerId, id);
    }

    @PostMapping("/runs/{id}/complete")
    public ModelVersionResponse complete(
            @RequestHeader("X-Trainer-Id") String trainerId,
            @PathVariable String id,
            @Valid @RequestBody CompleteTrainingRequest request) {
        return training.complete(trainerId, id, request);
    }

    @PostMapping("/runs/{id}/fail")
    public TrainingRunResponse fail(
            @RequestHeader("X-Trainer-Id") String trainerId,
            @PathVariable String id,
            @Valid @RequestBody FailTrainingRequest request) {
        return training.fail(trainerId, id, request.message());
    }

    @PostMapping("/inferences/claim")
    public ResponseEntity<ClaimedInference> claimInference(@RequestHeader("X-Trainer-Id") String trainerId) {
        return drafts.claim(trainerId)
                .map(ResponseEntity::ok)
                .orElseGet(() -> ResponseEntity.noContent().build());
    }

    @PostMapping("/inferences/{id}/complete")
    public ResponseEntity<Void> completeInference(
            @RequestHeader("X-Trainer-Id") String trainerId,
            @PathVariable String id,
            @Valid @RequestBody CompleteInferenceRequest request) {
        drafts.complete(trainerId, id, request.label());
        return ResponseEntity.noContent().build();
    }

    @PostMapping("/inferences/{id}/fail")
    public ResponseEntity<Void> failInference(
            @RequestHeader("X-Trainer-Id") String trainerId,
            @PathVariable String id,
            @Valid @RequestBody FailTrainingRequest request) {
        drafts.fail(trainerId, id, request.message());
        return ResponseEntity.noContent().build();
    }
}
