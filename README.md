# MusicMuse

MusicMuse is a comprehensive music analytics platform designed to help users gain deep insights into their listening habits and musical preferences.

## Components

- **Main App**: The core Flask application that provides the user interface and main functionality
- **Live Scrobbler**: A microservice for real-time Spotify scrobbling
- **Scripts**: Database optimization and maintenance scripts

## Getting Started

See the README.md in each component directory for specific setup instructions.

## Infrastructure

The project is designed to be deployed on DigitalOcean with the following components:
- PostgreSQL database
- Redis for caching and message brokering
- Main application and Live Scrobbler services
- DigitalOcean Spaces for object storage

## License

MIT