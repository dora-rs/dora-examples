#include "build/node_api.h"
#include <assert.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>

int main() {
  printf("[c node] Hello World\n");
  size_t counter = 0;

  void *dora_context = init_dora_context_from_env();
  if (dora_context == NULL) {
    fprintf(stderr, "failed to init dora context\n");
    return -1;
  }

  printf("[c node] dora context initialized\n");

  while (1) {
    void *event = dora_next_event(dora_context);
    if (event == NULL)
      {
        printf("[c node] ERROR: unexpected end of event\n");
        return -1;
      }

    enum DoraEventType ty = read_dora_event_type(event);

    if (ty == DoraEventType_Input) {
      char *id;
      size_t id_len;
      read_dora_input_id(event, &id, &id_len);
          
      if (strcmp(id, "message") == 0) {
        printf("message event\n");

        char *data;
        size_t data_len;
        read_dora_input_data(event, &data, &data_len);

        counter += 1;
        printf("C counter received message `%.*s`, counter: %zu\n", (int)data_len, data, counter);

        char *out_id = "counter";
        char *out_id_heap = strdup(out_id);

        int data_alloc_size = 100;
        char *out_data = (char *)malloc(data_alloc_size);
        int out_data_len = snprintf(out_data, data_alloc_size, "The current counter value is %zu", counter);
        assert(out_data_len >= 0 && out_data_len < 100);
        dora_send_output(dora_context, out_id, strlen(out_id), out_data, out_data_len);
      } else {
        printf("C counter received unexpected input %s, context: %zu\n", id, counter);
      }
    }
    else if (ty == DoraEventType_Stop) {
      printf("[c node] received stop event\n");
      break;
    } else {
      printf("[c node] received unexpected event: %d\n", ty);
    }

    free_dora_event(event);
  }

  printf("[c node] received 10 events\n");

  free_dora_context(dora_context);

  printf("[c node] finished successfully\n");

  return 0;
}
