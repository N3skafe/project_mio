package lab.maidops.project;

import com.fasterxml.jackson.annotation.JsonAlias;

public record CreateProjectRequest(
        String id,
        @JsonAlias("display_name") String name,
        String summary) {
}
