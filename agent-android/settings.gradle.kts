// Gradle settings for the Chimera Android agent.
// Single-module project; the agent is a thin app that captures the screen
// via MediaProjection and ships H.264 NAL units over WebSocket to the
// Chimera server.

pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}

rootProject.name = "ChimeraAgent"
include(":app")
