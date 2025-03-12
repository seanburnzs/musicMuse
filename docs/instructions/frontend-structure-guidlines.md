# Frontend Structure Guidelines

## Overview

The MusicMuse frontend utilizes a Flask/Jinja2 server-rendered approach with modern CSS and JavaScript for interactivity. The structure follows a template-based architecture with consistent styling and component patterns.

## Directory Structure

```
templates/
├── base.html             # Base template with common structure
├── index.html            # Home page
├── login.html            # Authentication
├── signup.html           # User registration
├── profile.html          # User profile views
├── top_items.html        # Analytics listings (tracks, albums, artists)
├── music_muse.html       # Natural language query interface
├── compare_profiles.html # User comparison
├── compare_select.html   # User selection for comparison
├── events.html           # Life events listing
├── event_form.html       # Event creation/editing
├── upload_data.html      # Data import interface
├── customize_hof.html    # Hall of Fame customization
└── settings.html         # User settings

static/
├── css/
│   ├── main.css          # Core styles
│   ├── auth.css          # Authentication styles
│   ├── profile.css       # Profile-related styles
│   └── musicMuse.css     # Music Muse specific styles
├── js/
│   └── [component].js    # Component-specific scripts
└── uploads/              # User-uploaded content
```

## Templates & Components

### Base Template (base.html)

The base template provides:
- Common page structure (header, navigation, footer)
- Meta tags and responsive viewport settings
- CSS and JavaScript includes
- User authentication state handling
- Impersonation functionality (for admin/testing)
- Flash message display

### Styling Principles

1. **Component-Based CSS**: Styles are organized by component with clear naming
2. **Responsive Design**: Mobile-first approach with media queries
3. **Color Scheme**: Purple-based (#5c6bc0) primary color with complementary palette
4. **Visual Hierarchy**: Clear typography scale and spacing system
5. **Interactive Elements**: Consistent hover/focus states for all interactive elements

### Component Patterns

#### Data Tables
- Used for displaying analytical data (top tracks, albums, artists)
- Support for sorting, pagination, and filtering
- Responsive design that adapts to small screens

#### Forms
- Consistent styling for input fields, labels, and buttons
- Clear validation states and error messages
- Responsive layouts for different screen sizes

#### Cards
- Used for discrete content blocks (events, profile items)
- Consistent padding, shadows, and border-radius
- Support for various content types and layouts

#### Filters
- Time range selection with custom date pickers
- Consistent dropdown styling and behavior
- Clear visual indication of active filters

#### Interactive Elements
- Buttons with hover/active states
- Dropdown menus for navigation and actions
- Modals for focused interactions

## JavaScript Usage

### General Guidelines

1. **Progressive Enhancement**: Core functionality works without JavaScript
2. **Event Delegation**: Efficient event handling for dynamic content
3. **Fetch API**: Used for AJAX requests instead of jQuery
4. **Error Handling**: Graceful degradation when requests fail
5. **Modular Structure**: Functions organized by responsibility

### Key JavaScript Features

- **Infinite Scrolling**: Loading additional content as user scrolls
- **Dynamic Filtering**: Real-time updates when filters change
- **Form Validation**: Client-side validation before submission
- **Interactive UI**: Toggles, modals, and responsive navigation
- **Data Visualization**: Chart rendering for analytics

## Responsive Design

### Breakpoints

- **Mobile**: Up to 768px
- **Tablet**: 769px to 1024px
- **Desktop**: 1025px and above

### Mobile Considerations

- Simplified navigation with dropdown menus
- Stack layouts instead of side-by-side
- Larger touch targets for buttons and links
- Optimized tables for smaller screens

## Accessibility Guidelines

1. **Semantic HTML**: Proper heading structure and ARIA roles
2. **Keyboard Navigation**: All interactive elements usable with keyboard
3. **Color Contrast**: Sufficient contrast between text and background
4. **Form Labels**: Explicit labels for all form fields
5. **Screen Reader Support**: Alt text for images and ARIA attributes

## Performance Optimization

1. **Minimal Dependencies**: Limited use of external libraries
2. **Efficient CSS**: Avoid deep nesting and overly-specific selectors
3. **Image Optimization**: Properly sized and compressed images
4. **Lazy Loading**: Load content as needed (especially for large lists)
5. **Pagination/Infinite Scroll**: Limit initial payload size
