# Tech Stack

## Backend Technologies

### Core Framework
- **Flask**: Python web framework used for the backend application
- **PostgreSQL**: Relational database to store user data, music listening history, and relationships
- **Redis**: In-memory data store for caching and session management

### Data Processing & Analytics
- **Celery**: Distributed task queue for background processing tasks
- **psycopg2**: PostgreSQL adapter for Python to interact with the database
- **Python Libraries**: datetime, json, logging, dotenv, werkzeug, and others

### Security
- **CSRF Protection**: Custom CSRF token implementation to protect against cross-site request forgery
- **Password Hashing**: werkzeug's generate_password_hash and check_password_hash for secure password storage
- **File Upload Security**: Secure file handling with size limits and type validation

### Natural Language Processing
- **Custom NLP Module**: Built-in musicnlp module with components for:
  - Query parsing (extracting intents, entities, time ranges)
  - Query analysis
  - Query execution against database
  - Response formatting

## Frontend Technologies

### Core Technologies
- **HTML/Jinja2 Templates**: Server-side templating for rendering dynamic content
- **CSS**: Custom styling with responsive design
- **JavaScript**: Client-side interactivity, AJAX requests, and dynamic UI updates
- **Font Awesome**: Icon library for visual elements

### User Interface Components
- **Modals**: For user interactions like impersonation
- **Dropdown Menus**: For navigation
- **Interactive Forms**: For data input and filtering
- **Infinite Scrolling**: For top items lists
- **Dynamic Data Filtering**: Time range selection and custom date ranges

## Infrastructure & Deployment

### Development Tools
- **dotenv**: Environment variable management
- **Git**: Version control

### Database Optimization
- **Materialized Views**: For optimizing complex analytical queries
- **Indexes**: On frequently queried columns
- **Constraints**: To ensure data integrity

### Scheduled Tasks
- **Database Maintenance**: Refreshing materialized views
- **Session Cleanup**: Removing old sessions

### API Support
- **JSON APIs**: For mobile client integration with endpoints for:
  - Top items retrieval
  - Natural language queries
  - User profile data

## Scaling Considerations
- **Caching Layer**: Redis implementation to reduce database load
- **Background Processing**: Celery for handling resource-intensive tasks
- **Database Optimization**: Materialized views and indexes for performance
- **API Architecture**: Clean separation for supporting multiple clients

## Planned Extensions
- **Mobile App Development**: Native mobile applications
- **Subscription Model**: Tiered access with premium features
- **Ad Integration**: For monetization
- **Apple Music Integration**: Expanding beyond current platform support
