package lab.maidops.job;

import java.util.List;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

public interface JobEventRepository extends JpaRepository<JobEventEntity, Long> {
    @Query("select coalesce(max(event.sequenceNo), 0) from JobEventEntity event where event.job.id = :jobId")
    int maxSequence(@Param("jobId") String jobId);

    List<JobEventEntity> findByJob_IdOrderBySequenceNoAsc(String jobId);

    List<JobEventEntity> findByJob_IdAndSequenceNoGreaterThanOrderBySequenceNoAsc(String jobId, int sequenceNo);

    @Query("""
            select distinct event.job from JobEventEntity event
            where lower(event.text) like lower(concat('%', :query, '%')) escape '\\'
            """)
    List<JobEntity> searchJobsByText(@Param("query") String query);
}
