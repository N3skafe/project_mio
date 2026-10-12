package lab.maidops.lab;

import java.time.Instant;
import java.util.List;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface TrainingRunRepository extends JpaRepository<TrainingRunEntity, String> {
    boolean existsByStatusIn(List<lab.maidops.domain.TrainingStatus> statuses);

    @Query("""
            select run from TrainingRunEntity run
            order by run.createdAt asc, run.id asc
            limit :limit
            """)
    List<TrainingRunEntity> firstPage(@Param("limit") int limit);

    @Query("""
            select run from TrainingRunEntity run
            where run.createdAt > :createdAt
                or (run.createdAt = :createdAt and run.id > :id)
            order by run.createdAt asc, run.id asc
            limit :limit
            """)
    List<TrainingRunEntity> pageAfter(
            @Param("createdAt") Instant createdAt,
            @Param("id") String id,
            @Param("limit") int limit);
}
