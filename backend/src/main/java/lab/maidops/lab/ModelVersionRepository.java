package lab.maidops.lab;

import java.time.Instant;
import java.util.List;
import java.util.Optional;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface ModelVersionRepository extends JpaRepository<ModelVersionEntity, String> {
    Optional<ModelVersionEntity> findByDefaultModelTrue();

    Optional<ModelVersionEntity> findFirstByOrderByCreatedAtDescIdDesc();

    @Query("""
            select model from ModelVersionEntity model
            order by model.createdAt asc, model.id asc
            limit :limit
            """)
    List<ModelVersionEntity> firstPage(@Param("limit") int limit);

    @Query("""
            select model from ModelVersionEntity model
            where model.createdAt > :createdAt
                or (model.createdAt = :createdAt and model.id > :id)
            order by model.createdAt asc, model.id asc
            limit :limit
            """)
    List<ModelVersionEntity> pageAfter(
            @Param("createdAt") Instant createdAt,
            @Param("id") String id,
            @Param("limit") int limit);
}
