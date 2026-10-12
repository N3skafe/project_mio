package lab.maidops.lab;

import java.util.List;

import org.springframework.data.jpa.repository.JpaRepository;

public interface TrainingExampleRepository extends JpaRepository<TrainingExampleEntity, Long> {
    List<TrainingExampleEntity> findByTrainingRunIdOrderByErrorCaseIdAsc(String trainingRunId);
}
