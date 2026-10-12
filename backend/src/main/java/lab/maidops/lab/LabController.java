package lab.maidops.lab;

import lab.maidops.api.PageResponse;
import lab.maidops.lab.LabPayloads.LabStatusResponse;
import lab.maidops.lab.LabPayloads.ModelVersionResponse;
import lab.maidops.lab.LabPayloads.TrainingRunResponse;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1")
public class LabController {
    private final TrainingService training;

    public LabController(TrainingService training) {
        this.training = training;
    }

    @GetMapping("/lab/status")
    public LabStatusResponse status() {
        return training.status();
    }

    @PostMapping("/training-runs")
    @ResponseStatus(HttpStatus.CREATED)
    public TrainingRunResponse create() {
        return training.createRun();
    }

    @GetMapping("/training-runs")
    public PageResponse<TrainingRunResponse> listRuns(
            @RequestParam(required = false) String cursor,
            @RequestParam(required = false) Integer limit) {
        return training.listRuns(cursor, limit);
    }

    @GetMapping("/training-runs/{id}")
    public TrainingRunResponse getRun(@PathVariable String id) {
        return training.getRun(id);
    }

    @PostMapping("/training-runs/{id}/cancel")
    public TrainingRunResponse cancel(@PathVariable String id) {
        return training.cancel(id);
    }

    @GetMapping("/model-versions")
    public PageResponse<ModelVersionResponse> listModels(
            @RequestParam(required = false) String cursor,
            @RequestParam(required = false) Integer limit) {
        return training.listModels(cursor, limit);
    }

    @PostMapping("/model-versions/{id}/select-default")
    public ModelVersionResponse selectDefault(@PathVariable String id) {
        return training.selectDefault(id);
    }
}
