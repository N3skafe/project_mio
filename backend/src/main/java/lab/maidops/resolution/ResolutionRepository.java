package lab.maidops.resolution;

import java.util.List;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface ResolutionRepository extends JpaRepository<ResolutionEntity, String> {
    @Query("""
            select record from ResolutionEntity record
            where lower(record.id) like lower(concat('%', :query, '%')) escape '\\'
               or lower(record.errorCaseId) like lower(concat('%', :query, '%')) escape '\\'
               or lower(record.projectId) like lower(concat('%', :query, '%')) escape '\\'
               or lower(record.cause) like lower(concat('%', :query, '%')) escape '\\'
               or lower(record.method) like lower(concat('%', :query, '%')) escape '\\'
            order by record.createdAt asc, record.id asc
            """)
    List<ResolutionEntity> search(@Param("query") String query);

    List<ResolutionEntity> findAllByOrderByCreatedAtAscIdAsc();
}
