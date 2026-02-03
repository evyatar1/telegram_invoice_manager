# **AI-Driven Invoice Processing and Classification System**
This microservices-based system automates the end-to-end process of extracting and
organizing data from invoice images. Users can upload invoices through a **Web Interface** or
send them via **Telegram**. The system then uses **OCR** and **OpenAI** to read the images, extract
key details like vendor names, dates, and amounts, and classify the information into a
structured format. To ensure smooth performance, the entire workflow is managed through
**Kafka**, which handles the image processing and data storage in a **PostgreSQL** database as an
asynchronous background task.


## **System Architecture**
The system is built using a containerized microservices architecture, orchestrated with **Docker
Compose**. It consists of the following components:

* **API Gateway (FastAPI):** Acts as the primary entry point for the **Web Interface**. It handles
image uploads and retrieves invoice status and data from the database.

* **Telegram Bot Service:** Manages incoming images from users via the Telegram Bot API
and forwards them to the processing pipeline.

* **Message Broker (Kafka):** Facilitates asynchronous communication. It decouples the
ingestion services (Web/Telegram) from the heavy processing workers, ensuring the
system remains responsive.

* **Invoice Processing Worker:** The core engine of the system. It consumes messages from
Kafka, performs **Image Pre-processing**, executes **OCR**, and uses **OpenAI** to parse and
classify the extracted text into structured data.

* **Database (PostgreSQL):** Provides persistent storage for user information and structured
invoice data. It is accessed via **SQLAlchemy Core** for optimized performance and data integrity.
