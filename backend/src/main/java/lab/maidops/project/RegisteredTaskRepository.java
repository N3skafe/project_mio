package lab.maidops.project;

import java.util.List;

import org.springframework.data.jpa.repository.JpaRepository;

public interface RegisteredTaskRepository extends JpaRepository<RegisteredTaskEntity, String> {
    List<RegisteredTaskEntity> findByProjectIdOrderByIdAsc(String projectId);
}
