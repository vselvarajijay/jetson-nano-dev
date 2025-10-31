#!/bin/bash

# VJEPA2 Service Runner Script
# This script safely starts the VJEPA2 inference service by:
# 1. Stopping any existing service containers
# 2. Ensuring clean environment
# 3. Building and starting the service with docker-compose

# Function to stop existing Docker containers
stop_existing_containers() {
    echo "🔍 Checking for existing VJEPA2 service containers..."
    
    # Find Docker containers running the service
    CONTAINER_IDS=$(docker ps -aq --filter "name=vjepa2-service")
    
    if [ -n "$CONTAINER_IDS" ]; then
        echo "⚠️  Found existing VJEPA2 service containers: $CONTAINER_IDS"
        echo "🛑 Stopping Docker containers..."
        
        for container_id in $CONTAINER_IDS; do
            echo "   Stopping container: $container_id"
            docker stop $container_id 2>/dev/null
        done
        
        sleep 2
        
        # Remove stopped containers
        docker rm $CONTAINER_IDS 2>/dev/null
        echo "✅ Existing containers stopped and removed"
    else
        echo "✅ No existing VJEPA2 service containers found"
    fi
}

# Function to check environment
check_environment() {
    echo "🔍 Checking environment..."
    
    # Check if we're in the right directory
    if [ ! -f "vjepa2-service/docker-compose.yml" ]; then
        echo "❌ Error: vjepa2-service/docker-compose.yml not found!"
        echo "Please run this script from the project root directory"
        exit 1
    fi
    
    # Check if Docker is available
    if ! command -v docker &> /dev/null; then
        echo "❌ Error: docker not found!"
        echo "Please install Docker"
        exit 1
    fi
    
    # Determine docker-compose command (set as global variable for other functions)
    if docker compose version &> /dev/null; then
        export DOCKER_COMPOSE="docker compose"
    elif command -v docker-compose &> /dev/null; then
        export DOCKER_COMPOSE="docker-compose"
    else
        echo "❌ Error: docker-compose not found!"
        echo "Please install docker-compose"
        exit 1
    fi
    
    echo "✅ Using: $DOCKER_COMPOSE"
    
    # Test Docker access
    if ! docker ps &> /dev/null; then
        echo "❌ Error: Cannot access Docker daemon!"
        echo "You may need to:"
        echo "  1. Run with sudo: sudo $0"
        echo "  2. Or reload the docker group: newgrp docker"
        echo "  3. Or add user to docker group: sudo usermod -aG docker $USER"
        exit 1
    fi
    
    # Check if nvidia-docker is available
    if ! docker info | grep -q nvidia; then
        echo "⚠️  Warning: nvidia runtime not detected"
        echo "Service will start without GPU access (may be slow)"
    else
        echo "✅ NVIDIA runtime detected"
    fi
    
    echo "✅ Environment checks passed"
}

# Function to check port availability
check_port() {
    echo "🔍 Checking if port 8000 is available..."
    
    if command -v lsof &> /dev/null; then
        if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null 2>&1; then
            echo "⚠️  Warning: Port 8000 is already in use"
            echo "   You may need to stop the existing service first"
            lsof -Pi :8000 -sTCP:LISTEN
        else
            echo "✅ Port 8000 is available"
        fi
    elif command -v netstat &> /dev/null; then
        if netstat -tuln | grep -q ":8000 "; then
            echo "⚠️  Warning: Port 8000 is already in use"
            echo "   You may need to stop the existing service first"
        else
            echo "✅ Port 8000 is available"
        fi
    else
        echo "⚠️  Cannot check port availability (lsof/netstat not available)"
    fi
}

# Function to start service with docker-compose
start_service() {
    echo "🚀 Starting VJEPA2 Service..."
    echo "================================"
    
    # Use docker-compose command from environment or determine it
    if [ -z "$DOCKER_COMPOSE" ]; then
        if docker compose version &> /dev/null; then
            DOCKER_COMPOSE="docker compose"
        elif command -v docker-compose &> /dev/null; then
            DOCKER_COMPOSE="docker-compose"
        else
            echo "❌ Error: docker-compose not found!"
            exit 1
        fi
    fi
    
    # Set up signal handler for graceful shutdown
    trap "echo -e '\n🛑 Received interrupt signal. Shutting down...'; cd vjepa2-service && $DOCKER_COMPOSE down; exit 0" INT TERM
    
    # Change to service directory
    cd vjepa2-service || {
        echo "❌ Error: Cannot change to vjepa2-service directory"
        exit 1
    }
    
    # Build Docker image
    echo "🔨 Building Docker image..."
    $DOCKER_COMPOSE build --no-cache
    
    if [ $? -ne 0 ]; then
        echo "❌ Docker build failed!"
        cd ..
        exit 1
    fi
    
    echo "✅ Docker image built successfully"
    echo ""
    
    # Start the service
    echo "🚀 Starting service container..."
    echo "   Service will be available at: http://localhost:8000"
    echo "   API docs: http://localhost:8000/docs"
    echo "   Health check: http://localhost:8000/health"
    echo ""
    echo "   Note: Model loading may take a few minutes on first start..."
    echo ""
    
    # Run docker-compose (foreground mode)
    $DOCKER_COMPOSE up
    
    # Check exit status
    EXIT_CODE=$?
    
    # Return to original directory
    cd ..
    
    if [ $EXIT_CODE -eq 0 ]; then
        echo "✅ Service exited normally"
    else
        echo "❌ Service exited with error code: $EXIT_CODE"
        exit $EXIT_CODE
    fi
}

# Function to start service in detached mode
start_service_detached() {
    echo "🚀 Starting VJEPA2 Service (detached mode)..."
    echo "=============================================="
    
    # Change to service directory
    cd vjepa2-service || {
        echo "❌ Error: Cannot change to vjepa2-service directory"
        exit 1
    }
    
    # Use docker-compose command from environment or determine it
    if [ -z "$DOCKER_COMPOSE" ]; then
        if docker compose version &> /dev/null; then
            DOCKER_COMPOSE="docker compose"
        elif command -v docker-compose &> /dev/null; then
            DOCKER_COMPOSE="docker-compose"
        else
            echo "❌ Error: docker-compose not found!"
            cd ..
            exit 1
        fi
    fi
    
    # Build Docker image if needed
    echo "🔨 Building Docker image (if needed)..."
    $DOCKER_COMPOSE build --no-cache
    
    if [ $? -ne 0 ]; then
        echo "❌ Docker build failed!"
        cd ..
        exit 1
    fi
    
    echo "✅ Docker image ready"
    echo ""
    
    # Start the service in detached mode
    echo "🚀 Starting service container (background)..."
    $DOCKER_COMPOSE up -d
    
    if [ $? -eq 0 ]; then
        echo "✅ Service started successfully"
        echo ""
        echo "   Service is running at: http://localhost:8000"
        echo "   API docs: http://localhost:8000/docs"
        echo "   Health check: http://localhost:8000/health"
        echo ""
        echo "   To view logs: cd vjepa2-service && $DOCKER_COMPOSE logs -f"
        echo "   To stop: cd vjepa2-service && $DOCKER_COMPOSE down"
    else
        echo "❌ Failed to start service"
        cd ..
        exit 1
    fi
    
    # Return to original directory
    cd ..
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  -h, --help      Show this help message"
    echo "  -d, --detached  Start service in detached mode (background)"
    echo "  -s, --stop      Stop the service"
    echo "  -l, --logs      Show service logs"
    echo "  -r, --restart   Restart the service"
    echo ""
    echo "Examples:"
    echo "  $0                    # Start service in foreground"
    echo "  $0 -d                 # Start service in background"
    echo "  $0 -s                 # Stop the service"
    echo "  $0 -l                 # Show service logs"
    echo "  $0 -r                 # Restart the service"
}

# Function to stop service
stop_service() {
    echo "🛑 Stopping VJEPA2 Service..."
    
    # Use docker-compose command from environment or determine it
    if [ -z "$DOCKER_COMPOSE" ]; then
        if docker compose version &> /dev/null; then
            DOCKER_COMPOSE="docker compose"
        elif command -v docker-compose &> /dev/null; then
            DOCKER_COMPOSE="docker-compose"
        else
            echo "❌ Error: docker-compose not found!"
            exit 1
        fi
    fi
    
    cd vjepa2-service || {
        echo "❌ Error: Cannot change to vjepa2-service directory"
        exit 1
    }
    
    $DOCKER_COMPOSE down
    
    cd ..
    echo "✅ Service stopped"
}

# Function to show logs
show_logs() {
    echo "📋 Showing VJEPA2 Service logs..."
    
    # Use docker-compose command from environment or determine it
    if [ -z "$DOCKER_COMPOSE" ]; then
        if docker compose version &> /dev/null; then
            DOCKER_COMPOSE="docker compose"
        elif command -v docker-compose &> /dev/null; then
            DOCKER_COMPOSE="docker-compose"
        else
            echo "❌ Error: docker-compose not found!"
            exit 1
        fi
    fi
    
    cd vjepa2-service || {
        echo "❌ Error: Cannot change to vjepa2-service directory"
        exit 1
    }
    
    $DOCKER_COMPOSE logs -f
    
    cd ..
}

# Function to restart service
restart_service() {
    echo "🔄 Restarting VJEPA2 Service..."
    stop_service
    sleep 2
    start_service_detached
}

# Parse command line arguments
DETACHED=false
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_usage
            exit 0
            ;;
        -d|--detached)
            DETACHED=true
            shift
            ;;
        -s|--stop)
            stop_service
            exit 0
            ;;
        -l|--logs)
            show_logs
            exit 0
            ;;
        -r|--restart)
            restart_service
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Main execution
main() {
    echo "🎬 VJEPA2 Service Runner"
    echo "========================"
    
    # Run safety checks
    stop_existing_containers
    check_environment
    check_port
    
    echo ""
    echo "🚀 All checks passed!"
    echo "===================="
    
    # Start the service
    if [ "$DETACHED" = true ]; then
        start_service_detached
    else
        echo ""
        start_service
    fi
}

# Run main function
main "$@"

