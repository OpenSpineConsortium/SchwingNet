The trainer's building blocks: each part of training is chosen by name with --block KEY=VALUE, and naming none gives version 1's training to the bit.

- The owner's ask of 2026-10-24: build the training improvements "as building block type pieces to make it interchangeable how i do something in case a better way arises" (#202).
- The parts and their names are src/schwingnet/blocks.py (normalise, augment, optimiser with weight_decay and backbone_lr_scale, schedule with warmup_epochs, sampler, loss_weights, select), with the pure arithmetic under the gate's contracts; the torch side is tools/train_blocks.py, one function per name in a table per part, and tests/test_train_blocks.py fails when a table and its tuple disagree.
- A new way of doing a part is one name added to its tuple in blocks.py and one function in its table in train_blocks.py; tools/train.py calls only the tables.
- tools/train.py takes --block KEY=VALUE, repeated; tools/flow.py takes the same and refuses a wrong one before any step. checkpoint.json and MODEL.md record the blocks, and the evaluator, the latency tool and the chain evaluation build the model with train.model_for(checkpoint facts), so a checkpoint from before the blocks loads as version 1's model.
- normalise=imagenet is a forward pre-hook on the model, not a layer, so the weights' names do not change and the ONNX export carries the scaling (parity tested).
- Which blocks a run uses is the owner's word with the run; no block changes a run that names none.
