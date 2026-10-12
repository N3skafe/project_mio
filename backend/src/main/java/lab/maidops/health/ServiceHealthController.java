package lab.maidops.health;

import java.sql.Timestamp;
import java.time.Instant;
import java.util.Map;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class ServiceHealthController {
    private final JdbcTemplate jdbcTemplate;
    private final int heartbeatWindowSeconds;

    public ServiceHealthController(
            JdbcTemplate jdbcTemplate,
            @Value("${maidops.worker-heartbeat-window-seconds:20}") int heartbeatWindowSeconds) {
        this.jdbcTemplate = jdbcTemplate;
        this.heartbeatWindowSeconds = heartbeatWindowSeconds;
    }

    @GetMapping("/api/v1/health")
    public ResponseEntity<Map<String, String>> health() {
        boolean databaseUp = probeDatabase();
        Map<String, String> body = Map.of(
                "status", databaseUp ? "UP" : "DOWN",
                "database", databaseUp ? "UP" : "DOWN",
                "worker", workerConnected() ? "CONNECTED" : "NOT_CONNECTED",
                "authentication", "NONE");
        return ResponseEntity.status(databaseUp ? 200 : 503).body(body);
    }

    private boolean workerConnected() {
        try {
            Integer count = jdbcTemplate.queryForObject(
                    "select count(*) from worker_sessions where last_heartbeat_at > ?",
                    Integer.class,
                    Timestamp.from(Instant.now().minusSeconds(heartbeatWindowSeconds)));
            return count != null && count > 0;
        } catch (RuntimeException exception) {
            return false;
        }
    }

    private boolean probeDatabase() {
        try {
            Integer value = jdbcTemplate.queryForObject("select 1", Integer.class);
            return value != null && value == 1;
        } catch (RuntimeException exception) {
            return false;
        }
    }
}
