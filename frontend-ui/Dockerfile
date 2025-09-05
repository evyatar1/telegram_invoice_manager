# frontend-ui/Dockerfile
# Stage 1: Build the React application
FROM node:18-alpine AS build

WORKDIR /app

COPY frontend-ui/package*.json ./
RUN npm install

COPY frontend-ui/ .
RUN npm run build

# Stage 2: Serve the application with Nginx
FROM nginx:alpine

# Copy the build output from the build stage to Nginx's public directory
COPY --from=build /app/build /usr/share/nginx/html

# Expose port 80 (Nginx default)
EXPOSE 80

# Command to run Nginx
CMD ["nginx", "-g", "daemon off;"]



## Dockerfile
#FROM node:18
#
#WORKDIR /app
#
#COPY package*.json ./
#RUN npm install
#
#COPY . .
#
#EXPOSE 3000
#
#CMD ["npm", "start"]
#
#
#
