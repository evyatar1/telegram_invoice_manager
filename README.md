## **AI-Driven Invoice Processing and Classification System**
This microservices-based system automates the end-to-end process of extracting and
organizing data from invoice images. Users can upload invoices through a **Web Interface** or
send them via **Telegram**. The system then uses **OCR** and **OpenAI** to read the images, extract
key details like vendor names, dates, and amounts, and classify the information into a
structured format. To ensure smooth performance, the entire workflow is managed through
**Kafka**, which handles the image processing and data storage in a **PostgreSQL** database as an
asynchronous background task.
