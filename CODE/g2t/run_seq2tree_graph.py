# coding: utf-8
import warnings
warnings.filterwarnings("ignore")

from src.train_and_evaluate import *
from src.models import *
import time
import torch.optim
from src.expressions_transfer import *
import json

def read_json(path):
    with open(path,'r') as f:
        file = json.load(f)
    return file


batch_size = 64
embedding_size = 128
hidden_size = 512
n_epochs = 80
learning_rate = 1e-3
weight_decay = 1e-5
beam_size = 5
n_layers = 2
ori_path = './data/english_'
#ori_path = './data/english_'
prefix = '_processed.json'

# ori_path = './data/'
# prefix = '23k_processed.json'
def get_train_test_fold(ori_path,prefix,data,pairs,group):
    # print("data",data[0])
    # print("pairs",pairs[0])
    # print("group",group[0])
    mode_train = 'train'
    mode_valid = 'valid'
    mode_test = 'test'
    train_path = ori_path + mode_train + prefix
    #valid_path = ori_path + mode_valid + prefix
    test_path = ori_path + mode_test + prefix
    train = read_json(train_path)
    train_id = [item['id'] for item in train]
    #valid = read_json(valid_path)
    #valid_id = [item['id'] for item in valid]
    test = read_json(test_path)
    #print(test[0])
    
    test_id = [item['id'] for item in test]
    test_ans = [item['answer'] for item in test]
    
    train_fold = []
    #valid_fold = []
    test_fold = []
    for item,pair,g in zip(data, pairs, group):
        pair = list(pair)
        pair.append(g['group_num'])
        pair.append(g['ans'])  #added by isha
        pair = tuple(pair)
        if item['id'] in train_id:
            train_fold.append(pair)
        elif item['id'] in test_id:
            test_fold.append(pair)
        #else:
            #valid_fold.append(pair)
    # print("train")
    # print(train_fold[0])
    # print("tets")
    # print(test_fold[0])
    return train_fold, test_fold#, valid_fold

def change_num(num):
    new_num = []
    for item in num:
        if '/' in item:
            new_str = item.split(')')[0]
            new_str = new_str.split('(')[1]
            a = float(new_str.split('/')[0])
            b = float(new_str.split('/')[1])
            value = a/b
            new_num.append(value)
        elif '%' in item:
            value = float(item[0:-1])/100
            new_num.append(value)
        else:
            new_num.append(float(item))
    return new_num


# data = load_raw_data("data/hindi.json")
group_data = read_json("data/english_processed.json")

data = load_raw_data("data/english.json")


#data = load_raw_data("data/english.json")
# group_data = read_json("data/english_processed.json")
# data = load_raw_data("data/english.json")  #full data train + test

pairs, generate_nums, copy_nums = transfer_num(data)

# print(pairs[0])
# print(generate_nums) #correct (only 2 and 100 for english dataset)
# quit()
temp_pairs = []


for p in pairs:
    temp_pairs.append((p[0], from_infix_to_prefix(p[1]), p[2], p[3])) #(segmented_text, 
                                                                            #eqn_template, quant, index_of_quant)
pairs = temp_pairs

# for p in pairs:
#     print("id:",p[4],"eqn", p[1])

train_fold, test_fold = get_train_test_fold(ori_path,prefix,data,pairs,group_data)

best_acc_fold = []

pairs_tested = test_fold # questions with equation
#pairs_trained = valid_fold
pairs_trained = train_fold #question without equations 
#for fold_t in range(5):
#    if fold_t == fold:
#        pairs_tested += fold_pairs[fold_t]
#    else:
#        pairs_trained += fold_pairs[fold_t]
# print(generate_nums)
# quit()

# print("pairs_tested: ", pairs_tested[0], len(pairs_tested[0]))
# print("pairs_trained: ", pairs_trained[0], len(pairs_trained[0]))

# for p in pairs_trained:
#     if(p[4]==2658): 
#         print(p)
#         quit()
# print(pairs_trained[5567])
# print(pairs_tested[0])
# quit()
input_lang, output_lang, train_pairs, test_pairs = prepare_data(pairs_trained, pairs_tested, 5, generate_nums,
                                                                copy_nums, tree=True)

# print("num_list",test_pairs[0][4])
# print("num stack:",test_pairs[0][6])

# print("xx",train_pairs[0])
# quit
#print(test_fold[0])
# print("input_lang",input_lang.index2word)
# print("output_lang", output_lang.index2word)
# print("train_pairs", train_pairs[0])
# print("test_pairs", test_pairs[0])

# Initialize models
encoder = EncoderSeq(input_size=input_lang.n_words, embedding_size=embedding_size, hidden_size=hidden_size,
                     n_layers=n_layers)
predict = Prediction(hidden_size=hidden_size, op_nums=output_lang.n_words - copy_nums - 1 - len(generate_nums),
                     input_size=len(generate_nums))
generate = GenerateNode(hidden_size=hidden_size, op_nums=output_lang.n_words - copy_nums - 1 - len(generate_nums),
                        embedding_size=embedding_size)
merge = Merge(hidden_size=hidden_size, embedding_size=embedding_size)
# the embedding layer is  only for generated number embeddings, operators, and paddings

encoder_optimizer = torch.optim.Adam(encoder.parameters(), lr=learning_rate, weight_decay=weight_decay)
predict_optimizer = torch.optim.Adam(predict.parameters(), lr=learning_rate, weight_decay=weight_decay)
generate_optimizer = torch.optim.Adam(generate.parameters(), lr=learning_rate, weight_decay=weight_decay)
merge_optimizer = torch.optim.Adam(merge.parameters(), lr=learning_rate, weight_decay=weight_decay)

encoder_scheduler = torch.optim.lr_scheduler.StepLR(encoder_optimizer, step_size=20, gamma=0.5)
predict_scheduler = torch.optim.lr_scheduler.StepLR(predict_optimizer, step_size=20, gamma=0.5)
generate_scheduler = torch.optim.lr_scheduler.StepLR(generate_optimizer, step_size=20, gamma=0.5)
merge_scheduler = torch.optim.lr_scheduler.StepLR(merge_optimizer, step_size=20, gamma=0.5)

# Move models to GPU
if USE_CUDA:
    encoder.cuda()
    predict.cuda()
    generate.cuda()
    merge.cuda()

generate_num_ids = []
for num in generate_nums:
    generate_num_ids.append(output_lang.word2index[num])

# print(generate_num_ids)
# print(output_lang.word2index)
# quit()


for epoch in range(n_epochs):

    encoder_scheduler.step()
    predict_scheduler.step()
    generate_scheduler.step()
    merge_scheduler.step()
    loss_total = 0
    input_batches, input_lengths, output_batches, output_lengths, nums_batches, \
    num_stack_batches, num_pos_batches, num_size_batches, num_value_batches, graph_batches = prepare_train_batch(train_pairs, batch_size)
    print("epoch:", epoch + 1)
    start = time.time()

    for idx in range(len(input_lengths)):
        # print("train num list",train_batch[4])
        loss = train_tree(
            input_batches[idx], input_lengths[idx], output_batches[idx], output_lengths[idx],
            num_stack_batches[idx], num_size_batches[idx], generate_num_ids, encoder, predict, generate, merge,
            encoder_optimizer, predict_optimizer, generate_optimizer, merge_optimizer, output_lang, num_pos_batches[idx], graph_batches[idx])
        loss_total += loss

    print("loss:", loss_total / len(input_lengths))
    print("training time", time_since(time.time() - start))
    print("--------------------------------")
    if epoch % 2 == 0 or epoch > n_epochs - 5:
        value_ac = 0
        equation_ac = 0
        eval_total = 0
        start = time.time()
        # print("test_pairs[0]::::", test_pairs[0])
        # print("test_pairs[1]::::", test_pairs[1])
        # exit()
        for test_batch in test_pairs:
            # print("test_batch>>>>>>>>> ", test_batch)
            # exit()
            batch_graph = get_single_example_graph(test_batch[0], test_batch[1], test_batch[7], test_batch[4], test_batch[5])
            test_res = evaluate_tree(test_batch[0], test_batch[1], generate_num_ids, encoder, predict, generate,
                                     merge, output_lang, test_batch[5], batch_graph, beam_size=beam_size)
                       
            val_ac, equ_ac, _, _ = compute_prefix_tree_result(test_res, test_batch[2], output_lang, test_batch[4], test_batch[6], test_batch[8], test_batch[3])
            if val_ac:
                value_ac += 1
            if equ_ac:
                equation_ac += 1
            eval_total += 1
        print(equation_ac, value_ac, eval_total)
        print("test_answer_acc", float(value_ac) / eval_total)
        print("testing time", time_since(time.time() - start))
        print("------------------------------------------------------")
        torch.save(encoder.state_dict(), "model_traintest_eng/encoder")
        torch.save(predict.state_dict(), "model_traintest_eng/predict")
        torch.save(generate.state_dict(), "model_traintest_eng/generate")
        torch.save(merge.state_dict(), "model_traintest_eng/merge")
        if epoch == n_epochs - 1:
            best_acc_fold.append((equation_ac, value_ac, eval_total))

a, b, c = 0, 0, 0
for bl in range(len(best_acc_fold)):
    a += best_acc_fold[bl][0]
    b += best_acc_fold[bl][1]
    c += best_acc_fold[bl][2]
    print(best_acc_fold[bl])
print(a / float(c), b / float(c))